
import sys
import os

# Añadir ruta raíz para importar core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from core.security import cifrar

def encrypt_input(text):
    encrypted = cifrar(text)
    print(f"\n Texto Original: {text}")
    print(f" Texto Cifrado: {encrypted}\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        encrypt_input(sys.argv[1])
    else:
        print("Uso: python encrypt_credential.py 'texto_a_cifrar'")
