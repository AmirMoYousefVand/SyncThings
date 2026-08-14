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
        except Exception:
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

    def _tcp_listen_thread(self):
        while True:
            try:
                conn, addr = self.tcp_server.accept()
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

    def disconnect(self):
        self.connected = False
        if self.peer_socket:
            try:
                self.peer_socket.close()
            except:
                pass
        self.peer_socket = None

    def send_data_packet(self, data_type, data, progress_callback=None):
        if not self.connected or not self.peer_socket:
            return False
        try:
            header = struct.pack('>BQ', data_type, len(data))
            self.peer_socket.sendall(header)

            # Send data in chunks for progress bar
            chunk_size = 65536
            total = len(data)
            sent = 0

            while sent < total:
                chunk = data[sent:sent+chunk_size]
                self.peer_socket.send(chunk)
                sent += len(chunk)
                if progress_callback:
                    progress_callback(sent, total)

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
                if size > 0:
                    progress_cb = self.callbacks.get('on_progress')
                    data = self.recvall(conn, size, progress_callback=progress_cb)
                    if data:
                        if 'on_data_received' in self.callbacks:
                            self.callbacks['on_data_received'](data_type, data)
            except:
                break
        self.disconnect()
        if 'on_error' in self.callbacks:
            self.callbacks['on_error']("Connection lost.")

    def recvall(self, sock, n, progress_callback=None):
        data = bytearray()
        while len(data) < n:
            packet = sock.recv(min(n - len(data), 65536))
            if not packet:
                return None
            data.extend(packet)
            if progress_callback:
                progress_callback(len(data), n)
        return data
