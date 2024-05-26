import tkinter as tk
from tkinter import messagebox
import numpy as np
import requests
import socket
import threading
from PIL import Image


def address_to_tuple(addr):
    """
    Converts an address string to a tuple of IP and port.

    Args:
        addr (str): Address in the format 'ip:port'.

    Returns:
        tuple: Tuple containing IP and port.
    """
    ip = addr.split(":")[0]
    port = int(addr.split(":")[1])
    return ip, port


def tuple_to_address(ip, port):
    """
    Converts an IP and port to an address string.

    Args:
        ip (str): IP address.
        port (int): Port number.

    Returns:
        str: Address string in the format 'ip:port'.
    """
    return ip + ":" + str(port)


def create_tcp_server():
    """
    Creates a TCP server socket.

    Returns:
        tuple: Tuple containing the TCP server socket and the port number.
    """
    for port in range(TCP_PORT_START, TCP_PORT_END):
        try:
            tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_socket.bind(('', port))
            tcp_socket.listen(1)
            print(f"TCP server socket is listening on port {port}")
            return tcp_socket, port
        except OSError:
            continue
    else:
        print("No available port for TCP server socket in the specified range.")


def create_udp_server():
    """
    Creates a UDP server socket.

    Returns:
        tuple: Tuple containing the UDP server socket and the port number.
    """
    for port in range(UDP_PORT_START, UDP_PORT_END):
        try:
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.bind(('', port))
            print(f"UDP server socket is listening on port {port}")
            return udp_socket, port
        except OSError:
            continue
    else:
        print("No available port for UDP server socket in the specified range.")


SERVER_IP = "127.0.0.1"
SERVER_PORT = "80"
REGISTER_API = "http://" + SERVER_IP + ":" + SERVER_PORT + "/register"
GET_ALL_API = "http://" + SERVER_IP + ":" + SERVER_PORT + "/get-all"
GET_API = "http://" + SERVER_IP + ":" + SERVER_PORT + "/get?username="
TCP_PORT_START = 10000
TCP_PORT_END = 20000
UDP_PORT_START = 20000
UDP_PORT_END = 30000


def send_image(dest_ip, dest_port, dest_filename):
    """
    Sends an image to the specified destination IP and port.

    Args:
        dest_ip (str): Destination IP address.
        dest_port (str): Destination port.
        dest_filename (str): Filename of the image to send.
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        image = Image.open('./files/' + dest_filename)
    except FileNotFoundError:
        udp_socket.sendto(b'InvalidFile', (dest_ip, int(dest_port)))
        udp_socket.close()
        print("Invalid image file path!")
        return
    image_array = np.asarray(image)
    rows, columns, channels = image_array.shape
    print("Image Dimensions: " + str(rows) + " * " + str(columns))
    dimensions_message = f"{rows}:{columns}"
    udp_socket.sendto(dimensions_message.encode(), (dest_ip, int(dest_port)))
    image_data = image.tobytes()
    chunk_size = 1024
    total_chunks = (len(image_data) + chunk_size - 1) // chunk_size
    for i in range(total_chunks):
        if i == total_chunks - 1:
            chunk = image_data[i * chunk_size:]
        else:
            chunk = image_data[i * chunk_size: (i + 1) * chunk_size]
        udp_socket.sendto(chunk, (dest_ip, int(dest_port)))
    udp_socket.sendto(b'Finished', (dest_ip, int(dest_port)))
    udp_socket.close()
    print("Image Sent Successfully.")


def send_text(client_socket, dest_filename):
    """
    Sends a text file to the connected client.

    Args:
        client_socket (socket): Client socket.
        dest_filename (str): Filename of the text file to send.
    """
    try:
        with open('./files/' + dest_filename, 'rb') as file:
            file_data = file.read()
        client_socket.sendall(file_data)
        print("Text file Sent Successfully.")
    except FileNotFoundError:
        print("Invalid text file path!")


def downloader(udp_addr, target_addr, file_addr: str):
    """
    Downloads a file from the specified target address.

    Args:
        udp_addr (str): UDP address.
        target_addr (str): Target address to download from.
        file_addr (str): File address to download.
    """
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.connect(address_to_tuple(target_addr))
    message = udp_addr + ":" + file_addr
    if file_addr.endswith('txt'):
        tcp_socket.sendall(message.encode())
        with open('./downloaded/' + file_addr, 'wb') as file:
            while True:
                data = tcp_socket.recv(1024)
                if not data:
                    break
                file.write(data)
        print("Text file downloaded successfully.")
    else:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind(address_to_tuple(udp_addr))
        tcp_socket.sendall(message.encode())
        print(tcp_socket.recv(1024).decode("utf-8"))
        dimensions_message, addr = udp_socket.recvfrom(1024)
        dimensions = dimensions_message.decode().split(":")
        rows = int(dimensions[0])
        columns = int(dimensions[1])
        print("Image Dimensions: " + str(rows) + " * " + str(columns))
        received_rows = []
        while True:
            input_data, addr = udp_socket.recvfrom(1024)
            if input_data == b'Finished':
                print("Downloading Image Finished.")
                break
            received_rows.append(input_data)
        udp_socket.close()
        image_data = b''.join(received_rows)
        image_array = np.frombuffer(image_data, dtype=np.uint8).reshape((rows, columns, -1))
        image = Image.fromarray(image_array)
        image.save('./downloaded/' + file_addr)
        tcp_socket.close()


def listener(server_socket):
    """
    Listens for incoming requests on the server socket.

    Args:
        server_socket (socket): Server socket to listen on.
    """
    while True:
        client_socket, client_address = server_socket.accept()
        input_data = client_socket.recv(1024).decode('utf-8')
        input_list = input_data.split(":")
        destination_ip = input_list[0]
        destination_port = input_list[1]
        destination_filename = input_list[2]
        is_accepted = handle_incoming_request(input_data)
        if is_accepted:
            client_socket.sendall(b"Accepted")
            if destination_filename.endswith('txt'):
                send_text(client_socket, destination_filename)
            elif destination_filename.endswith('jpg') or destination_filename.endswith('jpeg'):
                send_image(destination_ip, destination_port, destination_filename)
            else:
                client_socket.sendall(b"InvalidFormat")
        else:
            client_socket.sendall(b"Rejected")
        client_socket.close()


def start_gui():
    """
    Start the graphical user interface (GUI) for the application.

    """
    root = tk.Tk()
    root.configure(background="#333333")
    root.title("P2P File Sharing")
    root.geometry("400x600")

    init_label = tk.Label(root, text="1: Initialize", bg="#333333", fg="white")
    init_label.pack(pady=10)
    username_label = tk.Label(root, text="Username:", bg="#333333", fg="white")
    username_label.pack()
    global username_entry
    username_entry = tk.Entry(root)
    username_entry.pack()
    init_button = tk.Button(root, text="Register", command=handle_init, bg="green", fg="white")
    init_button.pack(pady=10)

    get_all_label = tk.Label(root, text="2: Get All Usernames", bg="#333333", fg="white")
    get_all_label.pack(pady=10)
    get_all_button = tk.Button(root, text="Get All", command=handle_get_all, bg="green", fg="white")
    get_all_button.pack(pady=10)

    get_label = tk.Label(root, text="3: Get Address", bg="#333333", fg="white")
    get_label.pack(pady=10)
    get_username_label = tk.Label(root, text="Username:", bg="#333333", fg="white")
    get_username_label.pack()
    global target_username_entry
    target_username_entry = tk.Entry(root)
    target_username_entry.pack()

    get_button = tk.Button(root, text="Get", command=handle_get, bg="green", fg="white")
    get_button.pack(pady=10)

    request_label = tk.Label(root, text="4: Request", bg="#333333", fg="white")
    request_label.pack(pady=10)
    download_username_label = tk.Label(root, text="Address:", bg="#333333", fg="white")
    download_username_label.pack()
    global target_address_entry
    target_address_entry = tk.Entry(root)
    target_address_entry.pack()
    download_file_label = tk.Label(root, text="File:", bg="#333333", fg="white")
    download_file_label.pack()
    global file_address_entry
    file_address_entry = tk.Entry(root)
    file_address_entry.pack()
    request_button = tk.Button(root, text="Request", command=handle_request, bg="green", fg="white")
    request_button.pack(pady=10)

    terminate_button = tk.Button(root, text="Terminate", command=root.destroy, bg="red", fg="white")
    terminate_button.pack(pady=10)

    threading.Thread(target=listener, args=(tcp_server_socket,)).start()

    root.mainloop()


def handle_init():
    """
    Handles the initialization (registration) process.
    """
    global username_entry
    username = username_entry.get()
    data = {
        "username": username,
        "address": TCP_ADDRESS
    }
    response = requests.post(REGISTER_API, json=data, verify=False)
    messagebox.showinfo("Response", response.text)
    print("Successfully Registered.")


def handle_get_all():
    """
    Handles the "Get All" request.
    """
    response = requests.get(GET_ALL_API)
    messagebox.showinfo("Response", response.text)
    print("Get All.")


def handle_get():
    """
    Handles the "Get" request.
    """
    global target_username_entry
    target_username = target_username_entry.get()
    response = requests.get(GET_API + target_username)
    messagebox.showinfo("Response", response.text)
    print("Get")


def handle_request():
    """
    Handles the file request process.
    """
    global target_address_entry, file_address_entry
    target_address = target_address_entry.get()
    file_address = file_address_entry.get()
    print("Request Sent to " + target_address + " for File " + file_address)
    threading.Thread(target=downloader, args=(UDP_ADDRESS, target_address, file_address)).start()


def handle_incoming_request(input_data):
    """
    Handles an incoming request.

    Args:
        input_data (str): Input data representing the incoming request.

    Returns:
        bool: True if the request is accepted, False otherwise.
    """
    print("Incoming Request")
    response = messagebox.askquestion("Incoming Request", f"Would you accept request {input_data}?")
    if response == 'yes':
        return True
    else:
        return False


if __name__ == "__main__":
    tcp_server_socket, tcp_port = create_tcp_server()
    udp_server_socket, udp_port = create_udp_server()
    TCP_ADDRESS = tuple_to_address(socket.gethostbyname(socket.gethostname()), tcp_port)
    UDP_ADDRESS = tuple_to_address(socket.gethostbyname(socket.gethostname()), udp_port)
    print("TCP Address: " + TCP_ADDRESS)
    print("UDP Address: " + UDP_ADDRESS)
    threading.Thread(target=listener, args=(tcp_server_socket,)).start()
    threading.Thread(target=listener, args=(udp_server_socket,)).start()
    start_gui()