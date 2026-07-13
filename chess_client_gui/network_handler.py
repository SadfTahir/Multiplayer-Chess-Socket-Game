# chess_client_gui/network_handler.py
import socket
import threading
import queue
import constants


class NetworkHandler:
    def __init__(self, message_queue):
        self.client_socket = None
        self.receive_thread = None
        self.stop_threads = False
        self.message_queue = message_queue  # Queue to send messages to the GUI thread

    def connect(self, host, port):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((host, port))
            self.message_queue.put(("LOG", f"Connected to server at {host}:{port}"))
            self.stop_threads = False
            self.receive_thread = threading.Thread(
                target=self._receive_loop, daemon=True
            )
            self.receive_thread.start()
            return True
        except ConnectionRefusedError:
            self.message_queue.put(
                ("ERROR", "Connection refused. Server might not be running.")
            )
            return False
        except Exception as e:
            self.message_queue.put(("ERROR", f"Error connecting: {e}"))
            return False

    def _receive_loop(self):
        while not self.stop_threads:
            try:
                message = self.client_socket.recv(4096).decode()
                if not message:
                    self.message_queue.put(("DISCONNECTED", "Received empty message."))
                    break
                for line in message.strip().split("\n"):
                    if line:
                        self.message_queue.put(("SERVER_MSG", line))
            except ConnectionResetError:
                self.message_queue.put(("DISCONNECTED", "Connection reset by server."))
                break
            except socket.timeout:  # If timeout is set on socket
                continue
            except socket.error as e:
                if not self.stop_threads:  # Avoid error if we initiated stop
                    self.message_queue.put(("DISCONNECTED", f"Socket error: {e}"))
                break  # Critical error
            except Exception as e:
                if not self.stop_threads:
                    self.message_queue.put(
                        ("LOG", f"Error receiving data: {e}")
                    )  # Log non-critical
                # Decide if this should break or continue
                break

        if not self.stop_threads:  # If loop exited unexpectedly
            self.message_queue.put(("LOG", "Receive thread stopped unexpectedly."))
        else:
            self.message_queue.put(("LOG", "Receive thread terminated normally."))

    def send_message(self, message):
        if self.client_socket and not self.stop_threads:
            try:
                self.client_socket.sendall(message.encode())
                return True
            except socket.error as e:
                self.message_queue.put(("DISCONNECTED", f"Error sending message: {e}"))
                self.close_connection()  # Ensure connection is marked as closed
                return False
        return False

    def close_connection(self):
        self.stop_threads = True
        if self.client_socket:
            try:
                # self.client_socket.shutdown(socket.SHUT_RDWR) # More forceful
                self.client_socket.close()
            except socket.error:
                pass  # Ignore errors on close
            finally:
                self.client_socket = None

        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=0.5)  # Wait a bit for thread to finish
        self.message_queue.put(("LOG", "Network connection closed."))
