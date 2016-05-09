/*
 * com.h
 *
 *  Created on: 9 feb 2015
 *      Author: osannolik
 */

#ifndef COM_H_
#define COM_H_

#include <stdint.h>
#include "queue.h"
#include "uart.h"

#define COM_INTERFACE             (0)

#define COM_HDR_SIZE              (2)
#define COM_PACKET_OVERHEAD_SIZE  (1+COM_HDR_SIZE) // 1 is start byte

#define COM_INTERFACE_BITS        (4)
#define COM_ID_BITS               (8-COM_INTERFACE_BITS)
#define COM_NUMBER_OF_INTERFACES  (1<<COM_INTERFACE_BITS)
#define COM_NUMBER_OF_IDS         (1<<COM_ID_BITS)

#define COM_PACKET_START          's'

#define COM_BUFFER_RX_SIZE        (512)

typedef enum {
  COM_ERROR = 0,
  COM_WRITE_TO = 1,
  COM_READ_FROM = 2
} com_id_t;

enum {
  // Must start at 0 and be sequential 0,1,2... etc
  uart = 0,
  //radio,
  // my_new_port,
  COM_NUMBER_OF_PORTS
};

typedef enum {
  WAIT_FOR_START = 0,
  GET_HEADER,
  GET_SIZE,
  GET_DATA
} com_parser_state_t;

typedef union {
  uint8_t raw[COM_HDR_SIZE];
  struct {
    uint8_t interface : COM_INTERFACE_BITS;
    uint8_t id        : COM_ID_BITS;
    uint8_t size;
  };
} __attribute__((packed)) com_header_t;

typedef struct {
  com_header_t header;
  uint8_t* address;
  uint32_t len;
  uint8_t port;
} __attribute__((packed)) com_message_t;

typedef struct {
  com_parser_state_t state;
  com_message_t message;

  uint32_t (*send_hook)(uint8_t *, uint16_t);
  uint32_t (*receive_hook)(uint8_t **);

  uint8_t buffer_rx[COM_BUFFER_RX_SIZE];
  queue_t buffer_tx;
} com_port_handler_t;

typedef struct {
  void (*callback)(com_message_t *);
  uint8_t is_init;
} com_interface_t;

typedef struct {
  uint8_t *address;
  uint16_t len;
} __attribute__((packed)) com_commander_memory_range_t;


int com_init();
int com_enable_interface(uint8_t new_interface, void (*callback)(com_message_t *));
int com_disable_interface(uint8_t di_interface);

int com_receive_message(uint8_t port);
int com_parse_message(uint8_t *data, uint32_t len, uint8_t port);
int com_put_message(com_message_t *msg);
int com_send_messages(uint8_t port);
int com_handler();
int com_send_message_by_address(com_message_t *msg);
int com_commands_read(com_message_t *msg_request);
int com_commands_write(com_message_t *msg_request);
int com_commands_send_error(com_message_t *msg);

#endif /* COM_H_ */
