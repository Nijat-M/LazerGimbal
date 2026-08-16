/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body - MKS SERVO42C Closed-Loop Stepper Engine
  *                   with High-Speed USB CDC & USART Dual Telemetry
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "tim.h"
#include "gpio.h"
#include "usb_device.h"
#include "usbd_cdc_if.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <stdlib.h> // abs, atoi, atof
#include <string.h>
#include <stdio.h>
#include <math.h>   // fabsf
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */
typedef enum {
    STATE_IDLE,
    STATE_RECEIVING_POS,
    STATE_RECEIVING_TUNING,
    STATE_RECEIVING_COMMAND
} RxState;
/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define RX_BUFFER_SIZE 64
#define STEP_TIMER_HZ 10000.0f            // TIM2 STEP 脉冲调度频率
#define PID_CONTROL_HZ 50.0f              // 保留现有 50Hz PID 解算频率
#define PID_SUBTICKS_PER_CYCLE 200U       // 10kHz / 200 = 50Hz
#define MAX_STEP_RATE 9000.0f             // 最大 9000 steps/s (高达 ~1000°/s 极速追击)
#define MAX_STEP_ACCEL 10000.0f           // 最大加速度 10000 steps/s^2 (毫秒级起步与强力制动)
#define FRICTION_BREAKAWAY_RATE_X 120.0f  // X 轴克服静摩擦起步前馈 (中心区平滑线性衰减)
#define MAX_RATE_CHANGE_PER_CYCLE (MAX_STEP_ACCEL / PID_CONTROL_HZ)
#define TRACKING_SLOW_ZONE_PIXELS 20.0f   // 准星中心 20px 核心区
#define VISION_TIMEOUT_CYCLES 24U         // 含最多20ms对齐延迟，总超时不超过500ms
#define DEADZONE_PIXELS 5                 // 与上位机默认死区一致
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */

// PID 参数 (与上位机 GUI 实时同步)
volatile float Kp = 0.60f, Ki = 0.16f, Kd = 0.50f;

// USB 发布完整待处理包，TIM2 通过递增序号原子消费。
volatile int16_t pending_error_x = 0;
volatile int16_t pending_error_y = 0;
volatile uint8_t pending_fire = 0;
volatile uint32_t rx_packet_sequence = 0;
uint32_t consumed_packet_sequence = 0;

// 仅由 TIM2 修改的当前视觉误差与 PID 历史
int16_t current_error_x = 0;
int16_t current_error_y = 0;
int16_t prev_error_x = 0;
int16_t prev_error_y = 0;
int16_t prev_prev_error_x = 0;
int16_t prev_prev_error_y = 0;

// 电机速度规划与 10kHz 连续相位 DDA 状态
volatile uint16_t pid_subtick_counter = 0;
volatile float target_step_rate_x = 0.0f;
volatile float target_step_rate_y = 0.0f;
volatile float current_step_rate_x = 0.0f;
volatile float current_step_rate_y = 0.0f;
volatile float step_phase_x = 0.0f;
volatile float step_phase_y = 0.0f;
volatile uint8_t pulse_active_x = 0;
volatile uint8_t pulse_active_y = 0;

// 运行控制与安全标志
uint8_t current_fire = 0;
uint16_t vision_timeout_counter = 0;
uint8_t stop_holdoff_cycles = 0;
volatile uint8_t stop_requested = 0;  // 仅由 TIM2 消费并执行的急停请求

// 通讯接收状态机变量 (USB CDC 高速通道)
volatile RxState rx_state = STATE_IDLE;
char rx_buffer[RX_BUFFER_SIZE];
volatile uint8_t rx_index = 0;

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */
static float LimitTrackingRate(float pid_step_delta, int16_t error);
static float RampMotorRate(float current_rate, float target_rate);
static void RequestStop(void);
static void ApplyStopMotion(void);
static void ResetPosition(void);
void Process_Protocol_Byte(uint8_t byte);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
static float LimitTrackingRate(float target_rate, int16_t error)
{
    if (!isfinite(target_rate)) {
        return 0.0f;
    }

    float abs_error = fabsf((float)error);
    if (abs_error < (float)DEADZONE_PIXELS) {
        return 0.0f;
    }

    float rate_limit = MAX_STEP_RATE;
    if (abs_error < TRACKING_SLOW_ZONE_PIXELS) {
        rate_limit *= abs_error / TRACKING_SLOW_ZONE_PIXELS;
    }

    if (target_rate > rate_limit) target_rate = rate_limit;
    if (target_rate < -rate_limit) target_rate = -rate_limit;
    return target_rate;
}

static float RampMotorRate(float current_rate, float target_rate)
{
    if (!isfinite(current_rate) || !isfinite(target_rate)) {
        return 0.0f;
    }
    if (target_rate > MAX_STEP_RATE) target_rate = MAX_STEP_RATE;
    if (target_rate < -MAX_STEP_RATE) target_rate = -MAX_STEP_RATE;

    // 换向时必须先减速到零，禁止 STEP/DIR 瞬间反转。
    if ((current_rate > 0.0f && target_rate < 0.0f) ||
        (current_rate < 0.0f && target_rate > 0.0f)) {
        target_rate = 0.0f;
    }

    float difference = target_rate - current_rate;
    float next_rate = target_rate;
    if (fabsf(difference) > MAX_RATE_CHANGE_PER_CYCLE) {
        next_rate = current_rate + ((difference > 0.0f) ?
                                    MAX_RATE_CHANGE_PER_CYCLE :
                                    -MAX_RATE_CHANGE_PER_CYCLE);
    }

    if (next_rate > MAX_STEP_RATE) next_rate = MAX_STEP_RATE;
    if (next_rate < -MAX_STEP_RATE) next_rate = -MAX_STEP_RATE;
    return next_rate;
}

static void RequestStop(void)
{
    stop_requested = 1;
}

static void ApplyStopMotion(void)
{
    current_error_x = 0;
    current_error_y = 0;
    prev_error_x = 0;
    prev_error_y = 0;
    prev_prev_error_x = 0;
    prev_prev_error_y = 0;
    consumed_packet_sequence = rx_packet_sequence;
    target_step_rate_x = 0.0f;
    target_step_rate_y = 0.0f;
    current_step_rate_x = 0.0f;
    current_step_rate_y = 0.0f;
    step_phase_x = 0.0f;
    step_phase_y = 0.0f;
    
    // 强制拉低脉冲引脚
    if (pulse_active_x) {
        HAL_GPIO_WritePin(GPIOA, X_STP_Pin, GPIO_PIN_RESET);
        pulse_active_x = 0;
    }
    if (pulse_active_y) {
        HAL_GPIO_WritePin(GPIOA, Y_STP_Pin, GPIO_PIN_RESET);
        pulse_active_y = 0;
    }
    
    current_fire = 0;
    vision_timeout_counter = 0;
    stop_holdoff_cycles = 3; // 丢弃 STOP 后约 60ms 内可能仍在传输的旧运动包
    stop_requested = 0;
}

static void ResetPosition(void)
{
    // 当前硬件没有原点开关；该命令只停止并重置控制状态。
    // 禁止在 USB 接收中断中调用 HAL_Delay，否则会阻塞 SysTick。
    RequestStop();
    HAL_GPIO_TogglePin(LED_GPIO_Port, LED_Pin);
}

/**
 * @brief 统一协议解析器 (全双工支持 USB CDC 与 USART)
 * @param byte 接收到的单字节
 */
void Process_Protocol_Byte(uint8_t byte)
{
    // STOP 抢占指令
    if (byte == '!') {
        rx_state = STATE_RECEIVING_COMMAND;
        rx_index = 0;
    }
    else if (rx_state == STATE_IDLE)
    {
        if (byte == '<') {
            rx_state = STATE_RECEIVING_POS;
            rx_index = 0;
        } else if (byte == '{') {
            rx_state = STATE_RECEIVING_TUNING;
            rx_index = 0;
        }
    }
    else if (rx_state == STATE_RECEIVING_POS)
    {
        if (byte == '>') {
            rx_buffer[rx_index] = '\0';
            
            // 解析 <Error_X,Error_Y,Fire>
            char *token1 = strtok((char*)rx_buffer, ",");
            char *token2 = strtok(NULL, ",");
            char *token3 = strtok(NULL, ",");
            
            if (token1 && token2 && token3) {
                int parsed_x = atoi(token1);
                int parsed_y = atoi(token2);
                
                // 工业级物理输入限幅：防止乱码或意外超大误差导致电机失控
                if (parsed_x > 400) parsed_x = 400;
                if (parsed_x < -400) parsed_x = -400;
                if (parsed_y > 400) parsed_y = 400;
                if (parsed_y < -400) parsed_y = -400;

                // 先写完整待处理数据，最后递增序号作为原子发布点。
                // TIM2 即使在写入中途抢占，也只会看到上一个完整序号。
                pending_error_x = (int16_t)parsed_x;
                pending_error_y = (int16_t)parsed_y;
                pending_fire = (uint8_t)atoi(token3);
                rx_packet_sequence++;
            }
            
            rx_state = STATE_IDLE;
        } else {
            if (rx_index < RX_BUFFER_SIZE - 1) {
                rx_buffer[rx_index++] = byte;
            } else {
                rx_state = STATE_IDLE; // overflow
            }
        }
    }
    else if (rx_state == STATE_RECEIVING_TUNING)
    {
        if (byte == '}') {
            rx_buffer[rx_index] = '\0';
            
            // 解析 {Kp,Ki,Kd}
            char *token1 = strtok((char*)rx_buffer, ",");
            char *token2 = strtok(NULL, ",");
            char *token3 = strtok(NULL, ",");
            
            if (token1 && token2 && token3) {
                float new_kp = (float)atof(token1);
                float new_ki = (float)atof(token2);
                float new_kd = (float)atof(token3);

                // 只接受 GUI 支持范围内的有限参数，防止 NaN/Inf 绕过限速。
                if (isfinite(new_kp) && isfinite(new_ki) && isfinite(new_kd) &&
                    new_kp >= 0.0f && new_kp <= 2.0f &&
                    new_ki >= 0.0f && new_ki <= 1.0f &&
                    new_kd >= 0.0f && new_kd <= 1.0f) {
                    Kp = new_kp;
                    Ki = new_ki;
                    Kd = new_kd;
                }
            }
            
            rx_state = STATE_IDLE;
        } else {
            if (rx_index < RX_BUFFER_SIZE - 1) {
                rx_buffer[rx_index++] = byte;
            } else {
                rx_state = STATE_IDLE; // overflow
            }
        }
    }
    else if (rx_state == STATE_RECEIVING_COMMAND)
    {
        if (byte == '\n' || byte == '\r') {
            rx_buffer[rx_index] = '\0';
            if (strcmp((char*)rx_buffer, "STOP") == 0) {
                RequestStop();
            } else if (strcmp((char*)rx_buffer, "CENTER") == 0) {
                ResetPosition();
            }
            rx_state = STATE_IDLE;
            rx_index = 0;
        } else if (rx_index < RX_BUFFER_SIZE - 1) {
            rx_buffer[rx_index++] = byte;
        } else {
            rx_state = STATE_IDLE;
            rx_index = 0;
        }
    }
}
/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_TIM2_Init();
  MX_USB_DEVICE_Init();
  
  /* USER CODE BEGIN 2 */
  // 启动 TIM2 10kHz 高频微步时钟中断
  HAL_TIM_Base_Start_IT(&htim2);
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  uint32_t last_led_tick = 0;
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
    // 心跳指示灯 (每 500ms 翻转一次，直观确认 STM32 正常运行)
    if (HAL_GetTick() - last_led_tick >= 500) {
        last_led_tick = HAL_GetTick();
        HAL_GPIO_TogglePin(LED_GPIO_Port, LED_Pin);
    }

    // 板载按键检测 (PA2) - Active Low (按下接地)
    if (HAL_GPIO_ReadPin(KEY_GPIO_Port, KEY_Pin) == GPIO_PIN_RESET) 
    {
        HAL_Delay(20); // 防抖
        if (HAL_GPIO_ReadPin(KEY_GPIO_Port, KEY_Pin) == GPIO_PIN_RESET)
        {
             ResetPosition();
             while(HAL_GPIO_ReadPin(KEY_GPIO_Port, KEY_Pin) == GPIO_PIN_RESET);
        }
    }
  }
  /* USER CODE END 3 */

}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE2);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  * 25MHz HSE:
  *   VCO_in  = 25MHz / 25 = 1.0 MHz
  *   VCO_out = 1.0MHz * 336 = 336.0 MHz
  *   SYSCLK  = 336.0MHz / 4 = 84.0 MHz (F401 Max)
  *   USB_CLK = 336.0MHz / 7 = 48.0 MHz (Exact USB Full-Speed)
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = 25;
  RCC_OscInitStruct.PLL.PLLN = 336;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV4;
  RCC_OscInitStruct.PLL.PLLQ = 7;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
  {
    Error_Handler();
  }
}

/* USER CODE BEGIN 4 */

/**
 * @brief 10kHz 硬件微步插补与 50Hz 增量 PID 核心中断回调
 */
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
  if (htim->Instance == TIM2)
  {
      // ==========================================================
      // [1] 脉冲清零 (Falling Edge: 保证 100μs 充沛的高电平脉宽)
      // ==========================================================
      if (pulse_active_x) {
          HAL_GPIO_WritePin(GPIOA, X_STP_Pin, GPIO_PIN_RESET);
          pulse_active_x = 0;
      }
      if (pulse_active_y) {
          HAL_GPIO_WritePin(GPIOA, Y_STP_Pin, GPIO_PIN_RESET);
          pulse_active_y = 0;
      }

      // 急停状态只由最高优先级 TIM2 修改，确保之后不再产生上升沿。
      if (stop_requested) {
          ApplyStopMotion();
          return;
      }

      // ==========================================================
      // [2] 连续相位 DDA 脉冲分配器 (Rising Edge)
      // 小数步跨 PID 周期保留，低速时不再发生 0/1 步量化跳变。
      // ==========================================================
      float abs_rate_x = fabsf(current_step_rate_x);
      if (abs_rate_x > 0.0f) {
          step_phase_x += abs_rate_x;
          if (step_phase_x >= STEP_TIMER_HZ) {
              step_phase_x -= STEP_TIMER_HZ;
              HAL_GPIO_WritePin(GPIOA, X_STP_Pin, GPIO_PIN_SET);
              pulse_active_x = 1;
          }
      }

      float abs_rate_y = fabsf(current_step_rate_y);
      if (abs_rate_y > 0.0f) {
          step_phase_y += abs_rate_y;
          if (step_phase_y >= STEP_TIMER_HZ) {
              step_phase_y -= STEP_TIMER_HZ;
              HAL_GPIO_WritePin(GPIOA, Y_STP_Pin, GPIO_PIN_SET);
              pulse_active_y = 1;
          }
      }

      // ==========================================================
      // [3] 50Hz 增量 PID 控制解算周期 (每 200 个 10kHz 滴答 = 20ms)
      // ==========================================================
      pid_subtick_counter++;
      if (pid_subtick_counter >= PID_SUBTICKS_PER_CYCLE)
      {
          pid_subtick_counter = 0;

          // STOP 后短暂丢弃串口中可能已经在途的旧运动包。
          if (stop_holdoff_cycles > 0U) {
              consumed_packet_sequence = rx_packet_sequence;
              stop_holdoff_cycles--;
              vision_timeout_counter = 0;
              return;
          }

          uint32_t latest_sequence = rx_packet_sequence;
          if (latest_sequence != consumed_packet_sequence) {
              // TIM2 优先级高于 USB；序号变化意味着待处理包已经完整写入。
              int16_t error_x = pending_error_x;
              int16_t error_y = pending_error_y;
              uint8_t fire = pending_fire;
              consumed_packet_sequence = latest_sequence;

              current_error_x = error_x;
              current_error_y = error_y;
              current_fire = fire;
              vision_timeout_counter = 0;

              // --------------------------------------------------
              // 3.1 工业级视觉伺服闭环速度规划 (自适应动态阻尼 + 平滑过渡前馈)
              // --------------------------------------------------
              float raw_rate_x = 0.0f;
              if (abs(error_x) >= DEADZONE_PIXELS) {
                  float abs_err_x = fabsf((float)error_x);
                  float error_diff_x = (float)(error_x - prev_error_x);

                  // 自适应微分阻尼：远距离低阻尼(25.0f)全速狂飙，近距离重度阻尼(160.0f)强效急刹定点
                  float d_gain_x = (abs_err_x < 25.0f) ? 160.0f : 25.0f;
                  raw_rate_x = (Kp * (float)error_x * 55.0f) + (Kd * error_diff_x * d_gain_x);

                  // 动态静摩擦前馈：在准星中心 15px 内平滑衰减至 0，彻底消除慢速过冲往复摆动！
                  float breakaway_x = (abs_err_x < 15.0f) ? (FRICTION_BREAKAWAY_RATE_X * (abs_err_x / 15.0f)) : FRICTION_BREAKAWAY_RATE_X;
                  if (raw_rate_x > 0.0f) {
                      raw_rate_x += breakaway_x;
                  } else if (raw_rate_x < 0.0f) {
                      raw_rate_x -= breakaway_x;
                  }
              }
              prev_prev_error_x = prev_error_x;
              prev_error_x = error_x;

              float raw_rate_y = 0.0f;
              if (abs(error_y) >= DEADZONE_PIXELS) {
                  float error_diff_y = (float)(error_y - prev_error_y);
                  // Y 轴保持柔和舒适手感 (18.0f / 70.0f)
                  raw_rate_y = (Kp * (float)error_y * 18.0f) + (Kd * error_diff_y * 70.0f);
              }
              prev_prev_error_y = prev_error_y;
              prev_error_y = error_y;

              target_step_rate_x = LimitTrackingRate(raw_rate_x, error_x);
              target_step_rate_y = LimitTrackingRate(raw_rate_y, error_y);
          } else {
              // 40Hz 上位机与 50Hz 固件之间的空周期保持目标速度；
              // 最后一包到达后最多 500ms 执行硬停止。
              vision_timeout_counter++;
              if (vision_timeout_counter >= VISION_TIMEOUT_CYCLES) {
                  ApplyStopMotion();
                  return;
              }
          }

          // ------------------------------------------------------
          // 3.4 电机执行层：加速度限制，并在换向前先减速到零
          // ------------------------------------------------------
          current_step_rate_x = RampMotorRate(current_step_rate_x, target_step_rate_x);
          current_step_rate_y = RampMotorRate(current_step_rate_y, target_step_rate_y);

          if (current_step_rate_x > 0.0f) {
              HAL_GPIO_WritePin(GPIOA, X_DIR_Pin, GPIO_PIN_SET);
          } else if (current_step_rate_x < 0.0f) {
              HAL_GPIO_WritePin(GPIOA, X_DIR_Pin, GPIO_PIN_RESET);
          } else {
              step_phase_x = 0.0f;
          }

          if (current_step_rate_y > 0.0f) {
              HAL_GPIO_WritePin(GPIOA, Y_DIR_Pin, GPIO_PIN_SET);
          } else if (current_step_rate_y < 0.0f) {
              HAL_GPIO_WritePin(GPIOA, Y_DIR_Pin, GPIO_PIN_RESET);
          } else {
              step_phase_y = 0.0f;
          }
      }
  }
}

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  NVIC_SystemReset();
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
