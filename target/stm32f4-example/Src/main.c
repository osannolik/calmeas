/*
 *  An application example where calmeas is used to measure and tune symbols. 
 *  Designed to work with the STM32F4-Discovery. See uart.h for pinout. 
 *
 *  Author: osannolik
 */

#include "main.h"
#include "math.h"
#include "calmeas.h"

// These five symbols will all be available for measurement and tuning
CALMEAS_SYMBOL(float,    phase_a,          0.0,  "Phase A current");
CALMEAS_SYMBOL(float,    phase_b,          0.0,  "Phase B current");
CALMEAS_SYMBOL(float,    phase_c,          0.0,  "Phase C current");
CALMEAS_SYMBOL(uint8_t,  red_led_sts,      0,    "Red LED status");
CALMEAS_SYMBOL(uint8_t,  red_led_set,      0,    "Set red LED on/off");
CALMEAS_SYMBOL(uint8_t,  green_led_set,    0,    "Set green LED on/off");
CALMEAS_SYMBOL(float,    green_led_period, 0.2,  "Period of green led blinking [s]");
CALMEAS_SYMBOL(float,    phase_a_amp,      10.0, "Amplitude of Phase A");

static void SystemClock_Config(void);
static void Error_Handler(void);
static void your_fantastic_application(void);
static void led_init(void);

int main(void)
{

  /* STM32F4xx HAL library initialization:
       - Configure the Flash prefetch, Flash preread and Buffer caches
       - Systick timer is configured by default as source of time base, but user 
             can eventually implement his proper time base source (a general purpose 
             timer for example or other time source), keeping in mind that Time base 
             duration should be kept 1ms since PPP_TIMEOUT_VALUEs are defined and 
             handled in milliseconds basis.
       - Low Level Initialization
     */
  HAL_Init();

  /* Configure the system clock to 168 MHz */
  SystemClock_Config();

  // Initialize peripherals used
  uart_init();

  // Initialize com-module
  com_init();

  // Initialize data structures used by calmeas
  calmeas_init();

  // Initialize stuff used by application
  led_init();



  while (1)
  {
    HAL_Delay(1);

    // calmeas handler should run periodically
    calmeas_handler();

    // com handler as well, preferably as often or more often than calmeas
    com_handler();

    // Do your magic!
    your_fantastic_application();
  }
}

void your_fantastic_application(void)
{
  static float t = 0;
  static float ticker = 0;
  static uint8_t toggle = 0;

  if (red_led_set) {
    RED_LED_SET;
  } else {
    RED_LED_RESET;
  }
  red_led_sts = red_led_set;

  if (green_led_set) {
    GREEN_LED_SET;
  } else {
    if (ticker >= green_led_period/2.0) {
      ticker = 0;
      if (toggle ^= 1)
        GREEN_LED_SET;
      else
        GREEN_LED_RESET;
    }
  }

  phase_a = phase_a_amp * cosf(6.28*1*t);
  phase_b = 10 * cosf(6.28*1*t - 6.28/3);
  phase_c = 10 * cosf(6.28*1*t + 6.28/3);

  ticker += 0.001;
  t += 0.001;
}

void led_init(void)
{
  GPIO_InitTypeDef GPIOinitstruct;

  __HAL_RCC_GPIOD_CLK_ENABLE();

  GPIOinitstruct.Speed = GPIO_SPEED_HIGH;
  GPIOinitstruct.Pull = GPIO_NOPULL;
  GPIOinitstruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIOinitstruct.Pin = RED_LED_PIN | GREEN_LED_PIN;

  HAL_GPIO_Init(RED_LED_PORT, &GPIOinitstruct);
}

/**
  * @brief  System Clock Configuration
  *         The system Clock is configured as follow : 
  *            System Clock source            = PLL (HSE)
  *            SYSCLK(Hz)                     = 168000000
  *            HCLK(Hz)                       = 168000000
  *            AHB Prescaler                  = 1
  *            APB1 Prescaler                 = 4
  *            APB2 Prescaler                 = 2
  *            HSE Frequency(Hz)              = 8000000
  *            PLL_M                          = 8
  *            PLL_N                          = 336
  *            PLL_P                          = 2
  *            PLL_Q                          = 7
  *            VDD(V)                         = 3.3
  *            Main regulator output voltage  = Scale1 mode
  *            Flash Latency(WS)              = 5
  * @param  None
  * @retval None
  */
static void SystemClock_Config(void)
{
  RCC_ClkInitTypeDef RCC_ClkInitStruct;
  RCC_OscInitTypeDef RCC_OscInitStruct;
  
  /* Enable Power Control clock */
  __HAL_RCC_PWR_CLK_ENABLE();
  
  /* The voltage scaling allows optimizing the power consumption when the device is 
     clocked below the maximum system frequency, to update the voltage scaling value 
     regarding system frequency refer to product datasheet.  */
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

  /* Enable HSE Oscillator and activate PLL with HSE as source */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = 8;
  RCC_OscInitStruct.PLL.PLLN = 336;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = 7;
  if(HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    /* Initialization Error */
    Error_Handler();
  }
  
  /* Select PLL as system clock source and configure the HCLK, PCLK1 and PCLK2 
     clocks dividers */
  RCC_ClkInitStruct.ClockType = (RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2);
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV4;  
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV2;  
  if(HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_5) != HAL_OK)
  {
    /* Initialization Error */
    Error_Handler();
  }

  /* STM32F405x/407x/415x/417x Revision Z devices: prefetch is supported  */
  if (HAL_GetREVID() == 0x1001)
  {
    /* Enable the Flash prefetch */
    __HAL_FLASH_PREFETCH_BUFFER_ENABLE();
  }
}
/**
  * @brief  This function is executed in case of error occurrence.
  * @param  None
  * @retval None
  */
static void Error_Handler(void)
{
  /* User may add here some code to deal with this error */
  while(1)
  {
  }
}

#ifdef  USE_FULL_ASSERT

/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t* file, uint32_t line)
{ 
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */

  /* Infinite loop */
  while (1)
  {
  }
}
#endif

