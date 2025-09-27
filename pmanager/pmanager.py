import sys
import json
import os
import subprocess
import pkg_resources
from pathlib import Path

# Configuración global
USER_CONFIG_DIR = Path.home() / ".pclibs_config"
USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = USER_CONFIG_DIR / "pmanager_config.json"

with pkg_resources.resource_stream(__name__, "libraries.json") as f:
    LIBRARIES = json.load(f)

def load_config():
    default = {
        "lib_path": Path.home() / ".pclibs",
        "pico_projects_path": Path.home() / "PicoProjects"
    }

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                user_config = json.load(f)
            for key in ["lib_path", "pico_projects_path"]:
                if key in user_config:
                    default[key] = Path(user_config[key])
        except json.JSONDecodeError:
            print("Archivo de configuración vacío o corrupto, usando valores por defecto.")

    # Normalizar rutas y crear carpetas
    for key in default:
        default[key] = default[key].expanduser().resolve()
        default[key].mkdir(parents=True, exist_ok=True)

    return default

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump({k: str(v) for k,v in config.items()}, f, indent=4)

config = load_config()

LIB_PATH = Path(config["lib_path"]).expanduser().resolve()
PP_PATH = Path(config.get("pico_projects_path", "")).expanduser().resolve()

os.makedirs(LIB_PATH, exist_ok=True)

def install(lib_name):
    
    repo_url = LIBRARIES.get(lib_name)

    if not repo_url:
        print(f"Librería '{lib_name}' no encontrada en libraries.json")
        return
    
    if lib_name.endswith(".git"):
        lib_name = lib_name[:-4]

    lib_dir = os.path.join(LIB_PATH, lib_name)
    if os.path.exists(lib_dir):
        print(f"Actualizando {lib_name}...")
        subprocess.run(["git", "-C", lib_dir, "pull"])
    else:
        print(f"Clonando {lib_name} desde {repo_url}...")
        subprocess.run(["git", "clone", repo_url, lib_dir])
    print(f"{lib_name} instalado")


def add_to_project(proyecto_name, lib_name):

    proyecto_path = os.path.join(PP_PATH, proyecto_name)

    if not os.path.exists(proyecto_path):
        print(f"Proyecto '{proyecto_name}' no encontrado en {PP_PATH}")
        return
    
    cmake_path = os.path.join(proyecto_path, "CMakeLists.txt")
    lib_path = os.path.join(LIB_PATH, lib_name).replace("\\", "/")

    add_subdir_line = f'add_subdirectory("{lib_path}" "${{CMAKE_BINARY_DIR}}/{lib_name}_build")\n'
    link_lib_line = f'target_link_libraries(${{PROJECT_NAME}} {lib_name})\n'

    with open(cmake_path, "r") as f:
        content = f.readlines()

    # Inserta add_subdirectory después de add_executable
    if add_subdir_line not in content:
        for i, line in enumerate(content):
            if "add_executable" in line:
                content.insert(i+1, add_subdir_line)
                break

    # Agrega el link de librería
    if link_lib_line not in content:
        for i, line in enumerate(content):
            if "target_link_libraries" in line:
                content[i] = line.strip() + f" {lib_name}\n"
                break

    with open(cmake_path, "w") as f:
        f.writelines(content)
    print(f"{lib_name} agregado al proyecto")


def list_libs():
    libs = [d for d in os.listdir(LIB_PATH) if os.path.isdir(os.path.join(LIB_PATH, d))]
    print("Librerías instaladas:")
    for l in libs:
        print(f" - {l}")


def list_pico_projects(): # tu función para cargar JSON
    root = config.get("pico_projects_path")
    if not root or not os.path.exists(root):
        print("Ruta de proyectos Pico no encontrada.")
        return []

    # Solo carpetas que contengan CMakeLists.txt (convención de proyecto Pico)
    projects = [d for d in os.listdir(root)
                if os.path.isdir(os.path.join(root, d))
                and os.path.exists(os.path.join(root, d, "CMakeLists.txt"))]
    return projects

def main():
    if len(sys.argv)<2:
        print("Usa un comando: install, add, list, setpath")
        return
    
    comando = sys.argv[1].lower()
    args = sys.argv[2:]
    
    if comando == "install":
        if len(args) != 1:
            print("Uso: pmanager install <repo_url>")
        else:
            install(args[0])

    elif comando == "add":
        if len(args) != 2:
            print("Uso: pmanager add <proyecto_path> <lib_name>")
        else:
            add_to_project(args[0], args[1])

    elif comando == "list":
        list_libs()

    elif comando == "pplist":
        print("Proyectos Pico encontrados:")
        projects= list_pico_projects()
        for p in projects:
            print(f" - {p}")

    else:
        print(f"Comando desconocido: {comando}")

if __name__ == "__main__":
    main()