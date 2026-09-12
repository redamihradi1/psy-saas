"""Génère une paire de clés VAPID pour les notifications push.

À lancer une seule fois par environnement (une fois en local, une fois sur
le serveur de prod — ne PAS réutiliser les mêmes clés partout si possible,
même si techniquement ça marcherait). Copie le résultat dans le fichier .env.

Usage : python scripts/generate_vapid_keys.py
"""
import base64

from py_vapid import Vapid02


def main():
    v = Vapid02()
    v.generate_keys()

    private_raw = v.private_key.private_numbers().private_value.to_bytes(32, 'big')
    private_b64 = base64.urlsafe_b64encode(private_raw).rstrip(b'=').decode()

    public_numbers = v.public_key.public_numbers()
    x = public_numbers.x.to_bytes(32, 'big')
    y = public_numbers.y.to_bytes(32, 'big')
    public_raw = b'\x04' + x + y
    public_b64 = base64.urlsafe_b64encode(public_raw).rstrip(b'=').decode()

    print("Ajoute ces lignes à ton fichier .env :\n")
    print(f"VAPID_PRIVATE_KEY={private_b64}")
    print(f"VAPID_PUBLIC_KEY={public_b64}")
    print("VAPID_ADMIN_EMAIL=ton-email@exemple.com")


if __name__ == '__main__':
    main()
