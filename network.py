import socket
import threading
import json
import struct
import time

TCP_PORT = 49152
UDP_PORT = 49153
MAGIC_WORD = b"SYNC_THINGS_V2:"

class NetworkManager:
    def __init__(self, app_id, callbacks):
        self.app_id = app_id
        self.callbacks = callbacks
        self.profile_name = ""
        self.avatar_b64 = None
        self.peer_socket = None
        self.connected = False

        self.tcp_server = None
        self.udp_socket = None
        self.discovery_running = False

        self.pause_event = threading.Event()
        self.pause_event.set()  # Set means not paused
        self.cancel_event = threading.Event()

    def get_local_ips(self):
        ips = []
        try:
            for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
                if not ip.startswith("127."):
                    ips.append(ip)
        except:
            pass
        return ips

    def update_profile_name(self, name, avatar_b64=None):
        self.profile_name = name
        self.avatar_b64 = avatar_b64

    def start_network(self):
        # Allow reusing the address on Windows for TCP if it crashed previously
        self.tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # TCP Optimization for listen socket - inherit to accepted sockets
            self.tcp_server.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception as e:
            import logging
            logging.error(f"Error setting TCP socket options on server: {e}")
            pass
        self.tcp_server.bind(("0.0.0.0", TCP_PORT))
        self.tcp_server.listen(5)
        threading.Thread(target=self._tcp_listen_thread, daemon=True).start()

        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except Exception:
            pass
        self.udp_socket.bind(("0.0.0.0", UDP_PORT))
        self._udp_thread = threading.Thread(target=self._udp_listen_thread, daemon=True)
        self._udp_thread.start()

    def start_discovery(self, burst_mode=True):
        if self.discovery_running:
            return
        self.discovery_running = True

        # Ensure UDP listener is running when discovery starts
        # If it was stopped, we might need to recreate the socket or thread
        # The prompt implies we need to be able to start/stop cleanly.
        # But for now, we just start the thread if it's not running
        # Actually, let's just make sure the _udp_listen_thread starts if needed.
        if not hasattr(self, '_udp_thread') or not self._udp_thread.is_alive():
            self._udp_thread = threading.Thread(target=self._udp_listen_thread, daemon=True)
            self._udp_thread.start()

        threading.Thread(target=self._broadcast_worker, args=(burst_mode,), daemon=True).start()

    def stop_discovery(self):
        self.discovery_running = False

    def _broadcast_worker(self, burst_mode):
        import profile
        import utils
        while self.discovery_running and not self.connected:
            try:
                mini_avatar = profile.get_mini_avatar_b64()
                payload = json.dumps({
                    "id": self.app_id,
                    "name": self.profile_name,
                    "mini_avatar": mini_avatar
                }).encode('utf-8')
                msg = MAGIC_WORD + payload

                self.udp_socket.sendto(msg, ("<broadcast>", UDP_PORT))
                self.udp_socket.sendto(msg, ("255.255.255.255", UDP_PORT))

                for ip, broadcast in utils.get_local_ips():
                    try:
                        self.udp_socket.sendto(msg, (broadcast, UDP_PORT))
                    except:
                        pass
            except:
                pass

            if burst_mode:
                # Loop 3 times rapidly
                for _ in range(2):
                    if not self.discovery_running or self.connected:
                        break
                    time.sleep(0.2)
                    try:
                        self.udp_socket.sendto(msg, ("<broadcast>", UDP_PORT))
                        self.udp_socket.sendto(msg, ("255.255.255.255", UDP_PORT))
                        for ip, broadcast in utils.get_local_ips():
                            try:
                                self.udp_socket.sendto(msg, (broadcast, UDP_PORT))
                            except:
                                pass
                    except:
                        pass
                burst_mode = False
            else:
                time.sleep(2)

    def _udp_listen_thread(self):
        self.udp_socket.settimeout(1.0)
        while self.discovery_running:
            try:
                # Increased buffer size to 65535 to prevent truncation of base64 mini avatars
                data, addr = self.udp_socket.recvfrom(65535)
                if data.startswith(MAGIC_WORD):
                    payload = data[len(MAGIC_WORD):].decode('utf-8')
                    try:
                        info = json.loads(payload)
                        peer_id = info.get("id")
                        peer_name = info.get("name", "Unknown")
                        mini_avatar = info.get("mini_avatar", "")
                    except:
                        continue

                    if peer_id != self.app_id:
                        if 'on_peer_discovered' in self.callbacks:
                            self.callbacks['on_peer_discovered'](addr[0], peer_name, peer_id, mini_avatar)
            except socket.timeout:
                pass
            except Exception:
                pass

    def _optimize_socket(self, conn):
        try:
            # TCP Optimization for sending/receiving on accepted connection
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            bufsize = 8388608  # 8MB
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, bufsize)
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, bufsize)
        except Exception as e:
            import logging
            logging.error(f"Failed to set optimized socket buffer options: {e}")

    def _tcp_listen_thread(self):
        while True:
            try:
                conn, addr = self.tcp_server.accept()
                try:
                    self._optimize_socket(conn)
                except Exception as e:
                    import logging
                    logging.error(f"Failed to set accepted socket buffer options: {e}")

                if not self.connected:
                    msg = conn.recv(1024)
                    if msg.startswith(b'PAIR_REQ'):
                        try:
                            # Try to extract name from payload if provided
                            payload = msg[len(b'PAIR_REQ:'):].decode('utf-8')
                            peer_info = json.loads(payload)
                            peer_name = peer_info.get("name", "Unknown")
                        except:
                            peer_name = "Unknown"

                        threading.Thread(target=self._handle_pairing_incoming, args=(conn, addr[0], peer_name), daemon=True).start()
                    else:
                        conn.close()
                else:
                    conn.close()
            except:
                pass

    def initiate_connection(self, ip, peer_name="Unknown"):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                self._optimize_socket(sock)
            except Exception as e:
                import logging
                logging.error(f"Failed to set socket buffer options: {e}")

            sock.settimeout(5)
            sock.connect((ip, TCP_PORT))
            sock.settimeout(None)

            # Send name with pairing request
            payload = json.dumps({"name": self.profile_name}).encode('utf-8')
            sock.sendall(b'PAIR_REQ:' + payload)

            response = sock.recv(1024)
            if response == b'YES':
                sock.sendall(b'YES')
                self._connect_success(sock, ip, peer_name)
            else:
                sock.close()
                if 'on_error' in self.callbacks:
                    self.callbacks['on_error']("Connection rejected by the other device.")
        except Exception as e:
            if 'on_error' in self.callbacks:
                self.callbacks['on_error'](f"Error connecting to {ip}")

    def _handle_pairing_incoming(self, sock, ip, peer_name):
        if 'on_connection_request' in self.callbacks:
            accepted = self.callbacks['on_connection_request'](ip, peer_name)
            if accepted:
                try:
                    sock.sendall(b'YES')
                    peer_response = sock.recv(1024)
                    if peer_response == b'YES':
                        self._connect_success(sock, ip, peer_name)
                    else:
                        sock.close()
                except:
                    sock.close()
            else:
                try:
                    sock.sendall(b'NO')
                except:
                    pass
                sock.close()
        else:
            sock.close()

    def _connect_success(self, sock, ip, peer_name="Unknown"):
        if self.connected:
            return
        self.peer_socket = sock
        self.connected = True
        self.stop_discovery()
        if 'on_connection_success' in self.callbacks:
            self.callbacks['on_connection_success'](ip, peer_name)

        threading.Thread(target=self._receive_data_thread, args=(sock,), daemon=True).start()

    def disconnect(self, send_signal=False):
        if send_signal and self.connected and self.peer_socket:
            try:
                # Send TYPE_DISCONNECT (9) with empty payload
                header = struct.pack('>BQ', 9, 0)
                self.peer_socket.sendall(header)
            except:
                pass
        self.connected = False
        self.cancel_transfer()
        if self.peer_socket:
            try:
                self.peer_socket.close()
            except:
                pass
        self.peer_socket = None

    def pause_transfer(self):
        self.pause_event.clear()

    def resume_transfer(self):
        self.pause_event.set()

    def cancel_transfer(self):
        self.cancel_event.set()
        self.resume_transfer() # Unblock if paused

    def reset_transfer_events(self):
        self.cancel_event.clear()
        self.pause_event.set()

    def send_file_packet(self, data_type, filepath, progress_callback=None):
        if not self.connected or not self.peer_socket:
            return False
        self.reset_transfer_events()
        import os
        total = os.path.getsize(filepath)
        try:
            header = struct.pack('>BQ', data_type, total)
            self.peer_socket.sendall(header)

            chunk_size = 4194304 # 4MB chunk size

            import logging
            import time
            logging.info(f"Sending file packet type {data_type} from disk (Size: {total/1048576:.2f} MB)")

            sent = 0
            last_cb_time = 0
            logging.info("Socket ready, starting to send chunks...")

            with open(filepath, 'rb') as f:
                if hasattr(os, 'sendfile') and os.name != 'nt':
                    # Unix
                    while sent < total:
                        if self.cancel_event.is_set():
                            raise Exception("Transfer cancelled by user")
                        self.pause_event.wait()

                        snt = os.sendfile(self.peer_socket.fileno(), f.fileno(), sent, min(total - sent, chunk_size))
                        if snt == 0:
                            break
                        sent += snt
                        now = time.time()
                        if progress_callback and (now - last_cb_time > 0.05 or sent >= total):
                            progress_callback(sent, total)
                            last_cb_time = now
                else:
                    # Windows or fallback
                    # Python's socket.sendfile without offset blocks the whole thread and breaks the UI,
                    # and falls back to a slow internal method anyway that causes speed drops.
                    # We use a highly optimized memoryview loop instead to avoid memory allocation overhead
                    # while maintaining granular UI updates.
                    buffer = bytearray(chunk_size)
                    view = memoryview(buffer)
                    while sent < total:
                        if self.cancel_event.is_set():
                            raise Exception("Transfer cancelled by user")
                        self.pause_event.wait()

                        bytes_read = f.readinto(buffer)
                        if not bytes_read:
                            break
                        self.peer_socket.sendall(view[:bytes_read])
                        sent += bytes_read
                        now = time.time()
                        if progress_callback and (now - last_cb_time > 0.05 or sent >= total):
                            progress_callback(sent, total)
                            last_cb_time = now

            logging.info("Finished sending all chunks.")
            return True
        except Exception as e:
            import logging
            logging.error(f"Error sending file packet: {e}", exc_info=True)
            self.disconnect()
            if 'on_error' in self.callbacks:
                self.callbacks['on_error']("Connection lost.")
            return False

    def send_data_packet(self, data_type, data, progress_callback=None):
        if not self.connected or not self.peer_socket:
            return False
        self.reset_transfer_events()
        try:
            header = struct.pack('>BQ', data_type, len(data))
            self.peer_socket.sendall(header)

            # Send data in chunks for progress bar
            total = len(data)
            if total <= 1048576:         # <= 1MB
                chunk_size = 65536       # 64KB
            elif total <= 52428800:      # <= 50MB
                chunk_size = 1048576     # 1MB
            else:
                chunk_size = 4194304     # 4MB

            import logging
            logging.info(f"Sending packet type {data_type} (Size: {total/1048576:.2f} MB, Chunking: {chunk_size/1024:.0f} KB)")

            sent = 0
            import time
            last_cb_time = 0

            while sent < total:
                if self.cancel_event.is_set():
                    raise Exception("Transfer cancelled by user")
                self.pause_event.wait()

                chunk = data[sent:sent+chunk_size]
                # CRITICAL: Must use sendall to prevent silent data loss if OS buffer is full
                self.peer_socket.sendall(chunk)
                sent += len(chunk)
                now = time.time()
                if progress_callback and (now - last_cb_time > 0.05 or sent >= total):
                    progress_callback(sent, total)
                    last_cb_time = now

            return True
        except:
            self.disconnect()
            if 'on_error' in self.callbacks:
                self.callbacks['on_error']("Connection lost.")
            return False

    def _receive_data_thread(self, conn):
        while self.connected:
            try:
                header = self.recvall(conn, 9)
                if not header:
                    break
                data_type, size = struct.unpack('>BQ', header)
                if data_type == 9: # TYPE_DISCONNECT
                    if 'on_peer_disconnected' in self.callbacks:
                        self.callbacks['on_peer_disconnected']()
                    break

                if size > 0:
                    import config
                    progress_cb = self.callbacks.get('on_progress')
                    if data_type == config.TYPE_FILES or data_type == config.TYPE_SINGLE_FILE:
                        import tempfile
                        import os
                        temp_file = tempfile.mktemp(suffix=".tmp")
                        success = self.recv_to_file(conn, size, temp_file, progress_callback=progress_cb)
                        if success:
                            if 'on_data_received' in self.callbacks:
                                self.callbacks['on_data_received'](data_type, temp_file)
                        else:
                            try:
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                            except:
                                pass
                    else:
                        self.reset_transfer_events()
                        data = self.recvall(conn, size, progress_callback=progress_cb)
                        if data:
                            if 'on_data_received' in self.callbacks:
                                self.callbacks['on_data_received'](data_type, data)
            except:
                break
        self.disconnect()
        if 'on_error' in self.callbacks:
            self.callbacks['on_error']("Connection lost.")

    def recv_to_file(self, sock, n, filepath, progress_callback=None):
        self.reset_transfer_events()
        import logging
        import time
        chunk_size = 4194304 # 4MB chunk
        logging.info(f"Receiving streaming file (Size: {n/1048576:.2f} MB, Chunking: {chunk_size/1024:.0f} KB) straight to {filepath}")

        received = 0
        last_cb_time = 0

        buffer = bytearray(chunk_size)
        view = memoryview(buffer)

        with open(filepath, 'wb') as f:
            while received < n:
                if self.cancel_event.is_set():
                    logging.error("Transfer cancelled by user")
                    self.disconnect(send_signal=True)
                    return False
                self.pause_event.wait()

                # Accumulate bytes in the 4MB buffer before writing to disk
                # This prevents thousands of tiny 1.5KB disk writes which kills SSD IOPS
                bytes_accumulated = 0
                target_read = min(n - received, chunk_size)

                while bytes_accumulated < target_read:
                    bytes_recv = sock.recv_into(view[bytes_accumulated:target_read], target_read - bytes_accumulated)
                    if not bytes_recv:
                        logging.error("Socket closed prematurely during receive.")
                        return False
                    bytes_accumulated += bytes_recv

                # Now do one massive, highly efficient write to the SSD
                f.write(view[:bytes_accumulated])
                received += bytes_accumulated

                now = time.time()
                if progress_callback and (now - last_cb_time > 0.05 or received >= n):
                    progress_callback(received, n)
                    last_cb_time = now

        logging.info("Finished receiving all chunks.")
        return True

    def recvall(self, sock, n, progress_callback=None):
        import logging
        if n <= 1048576:           # <= 1MB
            chunk_size = 65536     # 64KB
        elif n <= 52428800:        # <= 50MB
            chunk_size = 1048576   # 1MB
        else:
            chunk_size = 4194304   # 4MB

        logging.info(f"Receiving payload (Size: {n/1048576:.2f} MB, Chunking: {chunk_size/1024:.0f} KB) using zero-copy memoryview")

        data = bytearray(n)
        view = memoryview(data)
        received = 0

        while received < n:
            if self.cancel_event.is_set():
                logging.error("Transfer cancelled by user")
                return None
            self.pause_event.wait()

            to_read = min(n - received, chunk_size)
            packet_len = sock.recv_into(view[received:received+to_read], to_read)
            if packet_len == 0:
                return None
            received += packet_len
            if progress_callback:
                progress_callback(received, n)

        return data
