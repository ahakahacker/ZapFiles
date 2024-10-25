import asyncio
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from functools import partial
import shared_functions
import os


async def handle_client(reader, writer, filepath):
    try:
        # Получение публичного ключа клиента
        public_pem = await reader.read(450)
        public_key = serialization.load_pem_public_key(public_pem, backend=default_backend())

        # Генерация симметричного AES-ключа
        aes_key = os.urandom(32)

        # Шифрование AES-ключа с помощью публичного ключа клиента
        encrypted_aes_key = public_key.encrypt(
            aes_key,
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
        )

        # Отправка зашифрованного AES-ключа клиенту
        writer.write(encrypted_aes_key)
        await writer.drain()

        # Отправка размера файла клиенту
        file_size = os.path.getsize(filepath)
        writer.write(file_size.to_bytes(8, "big"))
        await writer.drain()

        # Шифрование и передача файла по частям
        aes_cipher = Cipher(algorithms.AES(aes_key), modes.CTR(b'0' * 16), backend=default_backend())
        encryptor = aes_cipher.encryptor()

        with open(filepath, "rb") as f:
            while True:
                file_data = f.read(4096)
                if not file_data:
                    break
                encrypted_file_data = encryptor.update(file_data)
                writer.write(encrypted_file_data)
                await writer.drain()

        writer.write(encryptor.finalize())
        await writer.drain()
        print("✅ File sent to client.")
    except Exception as e:
        print(f"❌ Error while handling client: {e}")
    finally:
        writer.close()
        await writer.wait_closed()


async def main():
    # Проверка наличия каталога с файлами
    server_files_dir = './server_files'
    if not os.path.exists(server_files_dir):
        print(f"❌ Directory '{server_files_dir}' does not exist. Exiting...")
        return

    # Настройка сервера
    print(
        "⚡ ZapFiles ⚡",
        "\n",
        "❗ Hosted files MUST be in './server_files'.",
    )

    key_ip = input("📝 Enter your IP address for key: ")
    host_to = "0.0.0.0"\
        if input("✉️ What network do you want to transfer files over?\n\n1. Public\n2. Local\n\n>> ") == "1"\
        else "localhost"

    filename = input("💽 Enter filename: ")
    filepath = f"{server_files_dir}/{filename}"
    if not os.path.exists(filepath):
        print("❌ File not found. Exiting...")
        return
    port = int(input("🚢 Enter port (default: 8888): ") or 8888)

    # Запуск сервера
    server_args = partial(handle_client, filepath=filepath)
    server = await asyncio.start_server(server_args, host_to, port)

    # Генерация публичного ключа сервера
    print(f"🔑 Server key: {key_ip}:{port}:{filename}:{shared_functions.get_file_hash(filepath)}")

    async with server:
        print("🌐 Server is running...")
        await server.serve_forever()


asyncio.run(main())
input()
