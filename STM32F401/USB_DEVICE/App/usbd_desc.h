/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : usbd_desc.h
  * @version        : v1.0_Cube
  * @brief          : Header for usbd_desc.c module.
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __USBD_DESC__H__
#define __USBD_DESC__H__

#ifdef __cplusplus
 extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "usbd_def.h"

#define DEVICE_ID1          (UID_BASE)
#define DEVICE_ID2          (UID_BASE + 0x4)
#define DEVICE_ID3          (UID_BASE + 0x8)

#define USB_SIZ_STRING_SERIAL       0x1A

/* Exported types ------------------------------------------------------------*/
extern USBD_DescriptorsTypeDef FS_Desc;

#ifdef __cplusplus
}
#endif

#endif /* __USBD_DESC__H__ */
