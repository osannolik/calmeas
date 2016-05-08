/*
 * cobs.h
 *
 *  Created on: 4 dec 2015
 *      Author: osannolik
 */

#ifndef COBS_H_
#define COBS_H_

#include <stdint.h>
#include <stddef.h>


#define COBS_FRAME_LEN_MAX (256)
#define COBS_OVERHEAD_MAX (1) // Use data len 254 byte maximum


uint8_t * cobs_Encode(const uint8_t *pData, uint32_t len, uint8_t *dst);
uint8_t cobs_Decode(const uint8_t *pCoded, uint32_t len, uint8_t *pData);


#endif /* COBS_H_ */
