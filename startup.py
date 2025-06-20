import os
import subprocess
import sys

def main():
    """Comando de inicio para Azure App Service"""
    # Ejecutar migraciones
    print("Ejecutando migraciones...")
    subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], check=True)
    
    # Recopilar archivos estáticos
    print("Recopilando archivos estáticos...")
    subprocess.run([sys.executable, "manage.py", "collectstatic", "--noinput"], check=True)
    
    print("Inicio completado exitosamente")

if __name__ == "__main__":
    main()