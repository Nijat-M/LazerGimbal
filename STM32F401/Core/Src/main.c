/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
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
#include "usart.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */
// --------------------------------------------------------------------------
// 工业级双轴伺服闭环变量与串口协议
// --------------------------------------------------------------------------
#include <stdlib.h> // atoi
#include <string.h>
#include <stdio.h>

typedef enum {
    STATE_IDLE,
    STATE_RECEIVING_POS,
    STATE_RECEIVING_TUNING
} RxState;
/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define SERVO_MIN_PULSE 600   // 对应约 0度
#define SERVO_MAX_PULSE 2400  // 对应约 180度
#define RX_BUFFER_SIZE 64
#define PID_INTEGRAL_MAX 200.0f   // 积分限幅
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */

// PID 参数 (与上位机初始化对齐)
volatile float Kp = 0.4f, Ki = 0.16f, Kd = 0.5f;

// 误差状态
volatile int16_t current_error_x = 0;
volatile int16_t current_error_y = 0;
volatile int16_t prev_error_x = 0;
volatile int16_t prev_error_y = 0;
volatile int16_t prev_prev_error_x = 0;
volatile int16_t prev_prev_error_y = 0;

volatile float integral_x = 0.0f;
volatile float integral_y = 0.0f;

// 舵机脉宽
volatile float servo_x_pulse = 1500.0f;
volatile float servo_y_pulse = 1500.0f;

volatile uint8_t current_fire = 0;
volatile uint8_t vision_timeout_counter = 0; 
volatile uint8_t new_data_flag = 0;   // 核心改进：防瞎积分的数据锁

// 串口变量
volatile RxState rx_state = STATE_IDLE;
uint8_t rx_byte;
char rx_buffer[RX_BUFFER_SIZE];
volatile uint8_t rx_index = 0;

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

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
  MX_USART1_UART_Init();
  /* USER CODE BEGIN 2 */
  // 启动定时器 PWM 输出
  HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1); // 启动舵机 X
  HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_2); // 启动舵机 Y

  // 开启 TIM2 的更新中断 (50Hz), 用于 PID 控制循环
  HAL_NVIC_SetPriority(TIM2_IRQn, 1, 0);
  HAL_NVIC_EnableIRQ(TIM2_IRQn);
  __HAL_TIM_ENABLE_IT(&htim2, TIM_IT_UPDATE);

  // 开启串口接收中断：告诉 STM32，“准备收这 1 个字节，收到了叫我”
  HAL_UART_Receive_IT(&huart1, &rx_byte, 1);
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
    // 简单的按键检测 (PA2) - Active Low (按下接地)
    if (HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_2) == GPIO_PIN_RESET) 
    {
        HAL_Delay(20); // 防抖
        if (HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_2) == GPIO_PIN_RESET)
        {
             // 归位 (Center)
             servo_x_pulse = 1500;
             servo_y_pulse = 1500;
             __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, 1500);
             __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_2, 1500);
             
             // 简单的 LED 闪烁提示
             HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_RESET); // On
             HAL_Delay(100);
             HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET);   // Off
             
             // 等待按键释放，防止重复触发
             while(HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_2) == GPIO_PIN_RESET);
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
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
  RCC_OscInitStruct.PLL.PLLM = 8;
  RCC_OscInitStruct.PLL.PLLN = 84;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = 4;
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

#define MAX_SERVO_DELTA 30.0f  // 核心提升：每次最大脉宽变化量（限幅步长），防止目标瞬移导致舵机抽搐扫齿

/**
 * @brief 工业级 PID 核心循环 (50Hz), 由定时器中断周期性挂载
 * 
 * 核心设计思想：
 * 1. 采用“增量式 PID”而非“位置式 PID”，天然免疫因为积分积累带来的积分饱和 (Integral Windup) 问题。
 * 2. 解耦异步数据通讯：只在拿到确切的新影像帧后计算补偿，杜绝瞎积分。
 */
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
  if (htim->Instance == TIM2)
  {
      // ==========================================================
      // [1] 安全看门狗 (Security Watchdog) - 防云台“锁死失控”
      // ==========================================================
      if (vision_timeout_counter < 100) { 
          vision_timeout_counter++;
      } else {
          // 超过100个Tick(即2秒)没有收到Python下发指令，认为目标丢失/程序崩溃。
          current_error_x = 0;
          current_error_y = 0;
          
          // ⚠️极限环境修复：必须同步清空历史状态！
          // 否则假设上一帧误差还是 50，这里突降为 0，这会导致 P项 `Kp*(0 - 50)` 输出巨大负向猛拉，云台会剧烈抖动。
          prev_error_x = 0; prev_prev_error_x = 0;
          prev_error_y = 0; prev_prev_error_y = 0;
          
          new_data_flag = 0; // 停机
      }

      // ==========================================================
      // [2] 异步数据防抖锁 (Asynchronous Data Lock)
      // ==========================================================
      // STM32中断频率极其恒定(50Hz)，但上位机因YOLO算力可能会掉到 30Hz 甚至偶尔卡顿。
      // 没有这把锁，STM32就会用“过期数据”重复多次积分。
      if (!new_data_flag) {
          return; // 暂无新指挥，维持原样不输出增量。
      }
      // 确认有新指令，下发计算通行证
      new_data_flag = 0;

      // ==========================================================
      // [3] 增量式 PID 姿态解算 (Incremental PID Core)
      // ==========================================================
      float delta_x = 0.0f;
      
      // 开启死区(Deadzone)：当目标在准星中心 3 像素以内时，不输出增量(不拉扯)，防止因像噪反复震荡。
      if (abs(current_error_x) >= 3) {
          /* 
           * 增量式PID标准公式: ΔU(k) = Kp*[e(k)-e(k-1)] + Ki*e(k) + Kd*[e(k) - 2e(k-1) + e(k-2)] 
           * 相比位置式直接计算出绝对坐标，这里解算的是“未来20ms云台需要的移动步数和方向 (Velocity)”
           */
          delta_x = Kp * (float)(current_error_x - prev_error_x) + 
                    Ki * (float)current_error_x + 
                    Kd * (float)(current_error_x - 2 * prev_error_x + prev_prev_error_x);
      }
      
      // ⚠️极限环境修复：无论是否在死区，历史误差状态(State History)必须无条件流转！
      // 若进入死区时冻结替换，则目标走出死区的第一帧时，e(k) 与 e(k-1) 的时间是不连续的，会引发剧烈的微分暴走(Derivative Kick)。
      prev_prev_error_x = prev_error_x;
      prev_error_x = current_error_x;

      float delta_y = 0.0f;
      if (abs(current_error_y) >= 3) {
          delta_y = Kp * (float)(current_error_y - prev_error_y) + 
                    Ki * (float)current_error_y + 
                    Kd * (float)(current_error_y - 2 * prev_error_y + prev_prev_error_y);
      }
      prev_prev_error_y = prev_error_y;
      prev_error_y = current_error_y;


      // ==========================================================
      // [4] Slew Rate Limiter (加速度/输出变化率限幅) - 专业级标配
      // ==========================================================
      // 极力保护机械结构：当目标突然闪现、或者PID算出了几百的极限增量时，强行切断为最大步长，保护舵机不被大电流烧毁或扫齿。
      if (delta_x > MAX_SERVO_DELTA) delta_x = MAX_SERVO_DELTA;
      if (delta_x < -MAX_SERVO_DELTA) delta_x = -MAX_SERVO_DELTA;
      if (delta_y > MAX_SERVO_DELTA) delta_y = MAX_SERVO_DELTA;
      if (delta_y < -MAX_SERVO_DELTA) delta_y = -MAX_SERVO_DELTA;


      // ==========================================================
      // [5] 执行积分叠加并物理限位 (Execution & Hard-Limits)
      // ==========================================================
      // 将本周期的计算增量，叠加在当下的真实物理 PWM 脉宽上。
      servo_x_pulse += delta_x;
      servo_y_pulse += delta_y;

      // 绝对死限位，防止撞死壳体 (500~2500 为典型180度舵机安全值)
      if(servo_x_pulse > SERVO_MAX_PULSE) servo_x_pulse = SERVO_MAX_PULSE;
      if(servo_x_pulse < SERVO_MIN_PULSE) servo_x_pulse = SERVO_MIN_PULSE;
      if(servo_y_pulse > SERVO_MAX_PULSE) servo_y_pulse = SERVO_MAX_PULSE;
      if(servo_y_pulse < SERVO_MIN_PULSE) servo_y_pulse = SERVO_MIN_PULSE;

      // 写出到底层寄存器
      __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, (uint32_t)servo_x_pulse);
      __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_2, (uint32_t)servo_y_pulse);
  }
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
  if(huart->Instance == USART1)
  {
    if (rx_state == STATE_IDLE)
    {
        if (rx_byte == '<') {
            rx_state = STATE_RECEIVING_POS;
            rx_index = 0;
        } else if (rx_byte == '{') {
            rx_state = STATE_RECEIVING_TUNING;
            rx_index = 0;
        }
    }
    else if (rx_state == STATE_RECEIVING_POS)
    {
        if (rx_byte == '>') {
            rx_buffer[rx_index] = '\0';
            
            // 解析 <Error_X,Error_Y,Fire>
            char *token1 = strtok((char*)rx_buffer, ",");
            char *token2 = strtok(NULL, ",");
            char *token3 = strtok(NULL, ",");
            
            if (token1 && token2 && token3) {
                current_error_x = atoi(token1);
                current_error_y = atoi(token2);
                
                // 核心改进：通知PID主循环有新数据可以做积分了
                new_data_flag = 1;
                
                vision_timeout_counter = 0; // 喂狗
            }
            
            rx_state = STATE_IDLE;
        } else {
            if (rx_index < RX_BUFFER_SIZE - 1) {
                rx_buffer[rx_index++] = rx_byte;
            } else {
                rx_state = STATE_IDLE; // overflow
            }
        }
    }
    else if (rx_state == STATE_RECEIVING_TUNING)
    {
        if (rx_byte == '}') {
            rx_buffer[rx_index] = '\0';
            
            // 解析 {Kp,Ki,Kd}
            char *token1 = strtok((char*)rx_buffer, ",");
            char *token2 = strtok(NULL, ",");
            char *token3 = strtok(NULL, ",");
            
            if (token1 && token2 && token3) {
                Kp = atof(token1);
                Ki = atof(token2);
                Kd = atof(token3);
                
                // 更换参数后通常需要重置积分
                integral_x = 0;
                integral_y = 0;
            }
            
            rx_state = STATE_IDLE;
        } else {
            if (rx_index < RX_BUFFER_SIZE - 1) {
                rx_buffer[rx_index++] = rx_byte;
            } else {
                rx_state = STATE_IDLE; // overflow
            }
        }
    }

    // 重新开启中断接收下一个字节
    HAL_UART_Receive_IT(&huart1, &rx_byte, 1);
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
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
