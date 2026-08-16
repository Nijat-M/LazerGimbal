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
#include <math.h>   // fabsf, roundf
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
#define PID_SUBTICKS_PER_CYCLE 200    // 10kHz 采样下，200 ticks = 20ms = 50Hz PID 周期
#define MAX_STEPS_PER_CYCLE 80.0f     // 单个 20ms 周期最大步数 (80步/20ms = 4000 steps/s 速度保护限幅)
#define DEADZONE_PIXELS 3             // 准星死区 (像素)
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */

// PID 参数 (与上位机 GUI 实时同步)
volatile float Kp = 0.4f, Ki = 0.16f, Kd = 0.5f;

// 视觉误差状态
volatile int16_t current_error_x = 0;
volatile int16_t current_error_y = 0;
volatile int16_t prev_error_x = 0;
volatile int16_t prev_error_y = 0;
volatile int16_t prev_prev_error_x = 0;
volatile int16_t prev_prev_error_y = 0;

// 10kHz 高频 DDA 脉冲分发器变量
volatile uint16_t pid_subtick_counter = 0;
volatile uint16_t steps_to_send_x = 0;
volatile uint16_t steps_to_send_y = 0;
volatile uint16_t step_accumulator_x = 0;
volatile uint16_t step_accumulator_y = 0;
volatile uint8_t pulse_active_x = 0;
volatile uint8_t pulse_active_y = 0;

// 运行控制与安全标志
volatile uint8_t current_fire = 0;
volatile uint16_t vision_timeout_counter = 0;
volatile uint8_t new_data_flag = 0;   // 异步数据锁：拿到新图像帧才做增量
volatile uint32_t control_epoch = 0;  // 抢占式急停纪元锁

// 通讯接收状态机变量 (USB CDC 高速通道)
volatile RxState rx_state = STATE_IDLE;
char rx_buffer[RX_BUFFER_SIZE];
volatile uint8_t rx_index = 0;

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */
static void StopMotion(void);
static void ResetPosition(void);
void Process_Protocol_Byte(uint8_t byte);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
static void StopMotion(void)
{
    control_epoch++;
    current_error_x = 0;
    current_error_y = 0;
    prev_error_x = 0;
    prev_error_y = 0;
    prev_prev_error_x = 0;
    prev_prev_error_y = 0;
    new_data_flag = 0;
    steps_to_send_x = 0;
    steps_to_send_y = 0;
    step_accumulator_x = 0;
    step_accumulator_y = 0;
    
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
}

static void ResetPosition(void)
{
    StopMotion();
    // 简单的 LED 闪烁提示
    HAL_GPIO_WritePin(LED_GPIO_Port, LED_Pin, GPIO_PIN_RESET); // On
    HAL_Delay(100);
    HAL_GPIO_WritePin(LED_GPIO_Port, LED_Pin, GPIO_PIN_SET);   // Off
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

                current_error_x = (int16_t)parsed_x;
                current_error_y = (int16_t)parsed_y;
                current_fire = (uint8_t)atoi(token3);
                
                new_data_flag = 1;
                vision_timeout_counter = 0; // 喂狗
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
                Kp = (float)atof(token1);
                Ki = (float)atof(token2);
                Kd = (float)atof(token3);
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
                StopMotion();
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

      // ==========================================================
      // [2] Bresenham / DDA 均匀脉冲分配器 (Rising Edge)
      // ==========================================================
      if (steps_to_send_x > 0) {
          step_accumulator_x += steps_to_send_x;
          if (step_accumulator_x >= PID_SUBTICKS_PER_CYCLE) {
              step_accumulator_x -= PID_SUBTICKS_PER_CYCLE;
              HAL_GPIO_WritePin(GPIOA, X_STP_Pin, GPIO_PIN_SET);
              pulse_active_x = 1;
          }
      }

      if (steps_to_send_y > 0) {
          step_accumulator_y += steps_to_send_y;
          if (step_accumulator_y >= PID_SUBTICKS_PER_CYCLE) {
              step_accumulator_y -= PID_SUBTICKS_PER_CYCLE;
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

          // ------------------------------------------------------
          // 3.1 安全看门狗 (2秒无有效视觉包自动挂起)
          // ------------------------------------------------------
          if (vision_timeout_counter < 100) {
              vision_timeout_counter++;
          } else {
              StopMotion();
          }

          // ------------------------------------------------------
          // 3.2 异步数据防瞎积分锁
          // ------------------------------------------------------
          if (!new_data_flag) {
              // 暂无新视觉帧，平滑刹车停发脉冲
              steps_to_send_x = 0;
              steps_to_send_y = 0;
              step_accumulator_x = 0;
              step_accumulator_y = 0;
              return;
          }
          new_data_flag = 0;
          uint32_t command_epoch = control_epoch;

          // ------------------------------------------------------
          // 3.3 增量式 PID 解算 (X 轴 & Y 轴)
          // ------------------------------------------------------
          float delta_x = 0.0f;
          if (abs(current_error_x) >= DEADZONE_PIXELS) {
              delta_x = Kp * (float)(current_error_x - prev_error_x) + 
                        Ki * (float)current_error_x + 
                        Kd * (float)(current_error_x - 2 * prev_error_x + prev_prev_error_x);
          }
          prev_prev_error_x = prev_error_x;
          prev_error_x = current_error_x;

          float delta_y = 0.0f;
          if (abs(current_error_y) >= DEADZONE_PIXELS) {
              delta_y = Kp * (float)(current_error_y - prev_error_y) + 
                        Ki * (float)current_error_y + 
                        Kd * (float)(current_error_y - 2 * prev_error_y + prev_prev_error_y);
          }
          prev_prev_error_y = prev_error_y;
          prev_error_y = current_error_y;

          // ------------------------------------------------------
          // 3.4 加速度 / 速度限幅 (Slew Rate Limiter)
          // ------------------------------------------------------
          if (delta_x > MAX_STEPS_PER_CYCLE) delta_x = MAX_STEPS_PER_CYCLE;
          if (delta_x < -MAX_STEPS_PER_CYCLE) delta_x = -MAX_STEPS_PER_CYCLE;
          if (delta_y > MAX_STEPS_PER_CYCLE) delta_y = MAX_STEPS_PER_CYCLE;
          if (delta_y < -MAX_STEPS_PER_CYCLE) delta_y = -MAX_STEPS_PER_CYCLE;

          // ------------------------------------------------------
          // 3.5 提交方向与微步脉冲数
          // ------------------------------------------------------
          if (command_epoch == control_epoch) {
              // 设置 X 轴方向 (PA4)
              HAL_GPIO_WritePin(GPIOA, X_DIR_Pin, (delta_x >= 0.0f) ? GPIO_PIN_SET : GPIO_PIN_RESET);
              // 设置 Y 轴方向 (PA5)
              HAL_GPIO_WritePin(GPIOA, Y_DIR_Pin, (delta_y >= 0.0f) ? GPIO_PIN_SET : GPIO_PIN_RESET);

              steps_to_send_x = (uint16_t)roundf(fabsf(delta_x));
              steps_to_send_y = (uint16_t)roundf(fabsf(delta_y));
              step_accumulator_x = 0;
              step_accumulator_y = 0;
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
