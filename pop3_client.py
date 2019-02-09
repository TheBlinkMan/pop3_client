import socket
from enum import Enum
import sys

def send_buffer(client_socket, msg_buffer, msg_buffer_size):
    total_sent  = 0
    while total_sent < msg_buffer_size:
        bytes_sent = client_socket.send(msg_buffer[total_sent:])
        if bytes_sent == 0:
            raise RuntimeError('socket connection broken')
        total_sent += bytes_sent

def read_line(client_socket):
    bytes_received = ''
    byte = None
    while byte != '\n':
        byte = client_socket.recv(1)
        try:
            byte = byte.decode()
            bytes_received += byte 
        except UnicodeDecodeError as e:
            pass
    return bytes_received

"""
Enum POP3_STATES
Contain all the possible states which an pop3 session may be in.
To have a pop3 session the client must open a tcp connection
with the pop3 server that's listening on the port 110
"""
class POP3_STATES(Enum):
    """
    When the server receives a command that its not known by the server.
    """
    INCORRECT = 0
    """
    When we establish a tcp connection we are in the authorization state.
    """
    AUTHORIZATION = 1
    """
    When the client successfully indentified itself we are in the transaction
    state.
    """
    TRANSACTION = 2
    """
    When the client issued the QUIT command we are in the update state,
    after this state the server updates the messages, releases the resources,
    and closes the tcp connection.
    """
    UPDATE = 3

class POP3_COMMANDS(Enum):
    USER = 0
    PASS = 1
    QUIT = 2
    STAT = 3
    LIST = 4
    RETR = 5
    DELE = 6
    RSET = 7
    NOOP = 8

"""
Input:  host a string containing the hostname or ip address of the server
        port an integer containing the port number 
Output: client_socket a socket connected to the server(host) on port
"""
def active_open(host, port):
        address = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        client_socket = socket.socket(family = socket.AF_INET,
                                           type=socket.SOCK_STREAM, proto=0)
        try:
            client_socket.connect(address[1][4])
        except ConnectionRefusedError as e:
            print('Connection Refused Try Again Later')
            client_socket.close()
            sys.exit(1)
        return client_socket

class Pop3Client:

    POP3_MESSAGES = {POP3_COMMANDS.USER : 'USER %s\r\n',
                     POP3_COMMANDS.PASS : 'PASS %s\r\n',
                     POP3_COMMANDS.QUIT : 'QUIT\r\n',
                     POP3_COMMANDS.STAT : 'STAT\r\n',
                     POP3_COMMANDS.LIST : 'LIST\r\n',
                     POP3_COMMANDS.RETR : 'RETR %s\r\n',
                     POP3_COMMANDS.DELE : 'DELE %s\r\n',
                     POP3_COMMANDS.RSET : 'RSET\r\n',
                     POP3_COMMANDS.NOOP : 'NOOP\r\n'}

    session_state = POP3_STATES.INCORRECT.value
    client_socket = None
    received_greeting = False

    def open_session(self, host, port):
        self.client_socket = active_open(host, port)

    def start_authorization(self):
        status = self.receive_line_greeting()
        if status == True:
            self.received_greeting = True
            self.session_state = POP3_STATES.AUTHORIZATION
            return True
        else:
            self.close_session()
            return False

    def receive_line_greeting(self):
        response = self.receive_response()
        status = self.get_response_status(response)
        return status

    def receive_response(self):
        buffer_received = read_line(self.client_socket)
        return buffer_received

    def receive_multline_response(self):
        response = ''
        while True:
            buffer_received = read_line(self.client_socket)
            if buffer_received == '.\r\n':
                break;
            response += buffer_received
        return response

    def check_credentials(self, user, password):
        self.send_compound_message(POP3_COMMANDS.USER, user)
        response = self.receive_response()
        self.send_compound_message(POP3_COMMANDS.PASS, password)
        response = self.receive_response()
        status = self.get_response_status(response)
        if status == True:
            self.session_state = POP3_STATES.TRANSACTION
        return status

    def get_maildrop_subjects(self, messages_number):
        messages = []
        for i in range(messages_number):
            pop3_client.send_compound_message(POP3_COMMANDS.RETR, i + 1)
            response = pop3_client.receive_multline_response()
            response_list = response.split('\r\n')
            message_content = []
            for i in range(len(response_list)):
                if response_list[i].startswith('Return-Path:'):
                    message_content.append(response_list[i].split()[1])
                    message_content.append(None)
                if response_list[i].lower().startswith('subject:'):
                    message_content[1] = response_list[i].split()[1]
            if message_content[1] == None:
                message_content[1] = 'No subject'
            messages.append(message_content)
        return messages

    def send_message(self, command):
        message_buffer = self.POP3_MESSAGES[command].encode('utf-8')
        send_buffer(self.client_socket, message_buffer, len(message_buffer))

    def send_compound_message(self, command, value):
        message_buffer = (self.POP3_MESSAGES[command] % format(value)).encode('utf-8')
        send_buffer(self.client_socket, message_buffer, len(message_buffer))

    """
    Input: response - The server response
    Output: Boolean value
            True if the status indicator is "+OK"
            False otherwise("-ERR")
    """
    def get_response_status(self, response):
        status = response[0:3]
        if status == '+OK':
            return True
        return False

    def close_session(self):
        self.send_message(POP3_COMMANDS.QUIT)
        print(self.receive_response())
        self.client_socket.close()

if __name__ == '__main__':
    print("Enter a hostname and port separed by a space:")
    try:
        host, port = input().split()
    except ValueError as e:
        print("Enter both, restart the application and try again")
        sys.exit(1)
    port = int(port)

    pop3_client = Pop3Client()
    pop3_client.open_session(host, port)
    if pop3_client.start_authorization() == False:
        print('The server you connected is having problems')
        sys.exit(1)


    print("Enter your username:")
    user = input()
    print("Enter your password:")
    password = input()
    if not pop3_client.check_credentials(user, password):
        print('User and Password dont match, restart the application and try again')
        pop3_client.client_socket.close()
        sys.exit(1)

    if pop3_client.session_state == POP3_STATES.TRANSACTION:
        pop3_client.send_message(POP3_COMMANDS.STAT)
        response = pop3_client.receive_response()
        deleted_messages = []
        if pop3_client.get_response_status(response) == True:
            messages_number = int(response.split()[1])
            print('You have ' + str(messages_number) + ' messages')

            messages = pop3_client.get_maildrop_subjects(messages_number)
            for i in range(messages_number):
                print('Message number: ' + str(i + 1) + ' from: ' + messages[i][0] + ' subject: ' + messages[i][1])

            while True:
                print('What message you would like to see? (type the number, 0 to quit)')
                try:
                    input_number = int(input())
                except ValueError as e:
                    print('You have to type a digit')
                    continue
                if input_number == 0:
                    pop3_client.close_session()
                    break;
                if input_number in deleted_messages or input_number > messages_number:
                    print('Message deleted or out of bounds')
                    continue
                pop3_client.send_compound_message(POP3_COMMANDS.RETR, input_number)
                response = pop3_client.receive_multline_response()
                if pop3_client.get_response_status(response) == True:
                    message_list = response.split('\r\n')
                    message_list = message_list[4:-1]
                    for i in range(len(message_list)):
                        print(message_list[i])
                print('Do you want to delete this message?y/n')
                answer = input()
                if answer == 'y':
                    pop3_client.send_compound_message(POP3_COMMANDS.DELE, input_number)
                    pop3_client.receive_response()
                    deleted_messages.append(input_number)
