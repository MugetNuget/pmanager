import sys
import json
import os
import subprocess
import pkg_resources
from pathlib import Path
import re
import shutil
import tkinter as tk
from tkinter import filedialog

# Configuración global
USER_CONFIG_DIR = Path.home() / ".pclibs_config"
USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = USER_CONFIG_DIR / "pmanager_config.json"

with pkg_resources.resource_stream(__name__, "libraries.json") as f:
    LIBRARIES = json.load(f)


"""
pmanager.py
Gestor de librerías y proyectos Pico para Raspberry Pi Pico.

Este script permite:
- Instalar librerías desde repositorios Git.
- Agregar y remover librerías de proyectos Pico.
- Inicializar entorno PicoLab para simulación.
- Convertir proyectos a modo desarrollo.
- Listar librerías instaladas y proyectos Pico disponibles.

Requiere Python 3 y Tkinter para selección de archivos JSON.
"""


def load_config():

    """
Carga la configuración del usuario desde CONFIG_FILE.
Diccionario con rutas normalizadas y creadas si no existían.
    """ 

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
    
    """
    Guarda la configuración del usuario en CONFIG_FILE.
    config Diccionario con rutas de librerías y proyectos.
    """
    with open(CONFIG_FILE, "w") as f:
        json.dump({k: str(v) for k,v in config.items()}, f, indent=4)

config = load_config()

LIB_PATH = Path(config["lib_path"]).expanduser().resolve()
PP_PATH = Path(config.get("pico_projects_path", "")).expanduser().resolve()

os.makedirs(LIB_PATH, exist_ok=True)


def install(lib_name):
    """
    Instala o actualiza una librería desde su repositorio Git.
    lib_name Nombre de la librería a instalar.
    """
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




def add_to_project(lib_name, proyecto_name):
    """
Agrega una librería a un proyecto Pico existente.
lib_name Nombre de la librería.
proyecto_name Nombre del proyecto Pico.
Modifica CMakeLists.txt para incluir add_subdirectory y target_link_libraries.
    """
    proyecto_path = PP_PATH / proyecto_name
    
    cmake_path = proyecto_path / "CMakeLists.txt"
    lib_path = LIB_PATH / lib_name

    if not proyecto_path.exists():
        print(f"❌ Proyecto '{proyecto_name}' no encontrado en {PP_PATH}")
        return
    if not cmake_path.exists():
        print(f"❌ No se encontró CMakeLists.txt en {proyecto_path}")
        return

    # línea add_subdirectory en formato POSIX (slash) apto para CMake
    lib_path_posix = lib_path.as_posix()
    add_subdir_line = f'add_subdirectory("{lib_path_posix}" "${{CMAKE_BINARY_DIR}}/{lib_name}_build")\n'

    content = cmake_path.read_text()

    # --- 1) Insertar add_subdirectory justo después de add_executable(...) si no existe ---
    if add_subdir_line.strip() not in content:
        m_exec = re.search(r"(add_executable\s*\(.*?\))", content, flags=re.DOTALL)
        if m_exec:
            insert_pos = m_exec.end()
            content = content[:insert_pos] + "\n" + add_subdir_line + content[insert_pos:]
        else:
            # si no hay add_executable, añadir al final
            content += "\n" + add_subdir_line

    # --- 2) Añadir lib_name dentro del bloque target_link_libraries(...) del target correcto ---
    pattern = re.compile(r"target_link_libraries\s*\((.*?)\)", flags=re.DOTALL)
    matches = list(pattern.finditer(content))

    chosen_match = None
    # preferir el bloque cuyo primer token (target) coincida con proyecto_name o ${PROJECT_NAME}
    for m in matches:
        inside = m.group(1).strip()
        tokens = re.findall(r'[^\s()]+', inside)
        if not tokens:
            continue
        target = tokens[0]
        if target == proyecto_name or target in ("${PROJECT_NAME}", "PROJECT_NAME"):
            chosen_match = m
            break
    # si no encontramos coincidencia exacta, tomar el primer bloque (si hay alguno)
    if chosen_match is None and matches:
        chosen_match = matches[0]

    if chosen_match:
        raw_inside = chosen_match.group(1)
        lines_inside = raw_inside.splitlines()

        # obtener target (primer token de la primer línea)
        first_tokens = re.findall(r'[^\s()]+', lines_inside[0]) if lines_inside else []
        target_name = first_tokens[0] if first_tokens else proyecto_name

        # recolectar posibles libs: solo tokens que no sean directivas o comentarios
        libs = []
        skip_keywords = re.compile(r'^(?:PRIVATE|PUBLIC|INTERFACE)$', flags=re.IGNORECASE)
        for idx, l in enumerate(lines_inside):
            s = l.strip()
            if not s:
                continue
            if s.startswith("#"):
                continue
            if s.startswith("target_"):  # p.ej. target_include_directories
                continue
            # si la primera línea contiene target + libs en la misma línea
            if idx == 0:
                parts = first_tokens[1:]  # tokens después del target
            else:
                # quitar paréntesis finales si existen y dividir en tokens
                s_clean = s.rstrip(")")
                parts = re.findall(r'[^\s()]+', s_clean)
            for p in parts:
                if skip_keywords.match(p):
                    continue
                if p.startswith("target_"):
                    continue
                if p.startswith("#"):
                    continue
                libs.append(p)

        # dedup manteniendo orden
        seen = set()
        libs_filtered = []
        for t in libs:
            if t not in seen:
                seen.add(t)
                libs_filtered.append(t)

        # agregar la nueva lib si no está
        if lib_name not in libs_filtered:
            libs_filtered.append(lib_name)

        # reconstruir bloque limpio (una lib por línea, indentadas)
        libs_str = "\n    ".join(libs_filtered) if libs_filtered else ""
        new_block = f"target_link_libraries({target_name}\n    {libs_str}\n)"

        # reemplazar el bloque seleccionado por el nuevo
        start, end = chosen_match.start(), chosen_match.end()
        content = content[:start] + new_block + content[end:]
    else:
        # no existía ningún bloque target_link_libraries -> añadir uno al final con el target pedido
        content += f"\ntarget_link_libraries({proyecto_name}\n    {lib_name}\n)\n"

    # Guardar cambios
    cmake_path.write_text(content)
    print(f"✅ {lib_name} agregado al proyecto '{proyecto_name}'")


def remove_from_project(lib_name, proyecto_name):
    """
Remueve una librería de un proyecto Pico existente.
lib_name Nombre de la librería.
proyecto_name Nombre del proyecto Pico.
Modifica CMakeLists.txt eliminando add_subdirectory y target_link_libraries.
    """
    proyecto_path = PP_PATH / proyecto_name
    cmake_path = proyecto_path / "CMakeLists.txt"

    if not proyecto_path.exists():
        print(f"Proyecto '{proyecto_name}' no encontrado en {PP_PATH}")
        return
    if not cmake_path.exists():
        print(f"No se encontró CMakeLists.txt en {proyecto_path}")
        return

    lines = cmake_path.read_text().splitlines()
    found = False
    new_lines = []
    inside_tll = False  # estamos dentro de un bloque target_link_libraries

    for line in lines:
        stripped = line.strip()

        # --- Quitar add_subdirectory con la lib ---
        if "add_subdirectory" in stripped and lib_name in stripped:
            found = True
            continue  # saltamos esa línea

        # --- Procesar target_link_libraries ---
        if stripped.startswith("target_link_libraries"):
            inside_tll = True

            # unimos toda la línea (puede ser multilínea)
            buffer = line
            continue

        if inside_tll:
            buffer += "\n" + line
            if ")" in stripped:  # fin del bloque
                inside_tll = False

                # procesar el bloque completo
                parts = buffer.replace("(", " ").replace(")", " ").split()
                # Ej: ["target_link_libraries", "Game", "pbinstr", "pico_stdlib"]
                filtered = [p for p in parts if p != lib_name]

                if len(filtered) > 2:  # quedan target + al menos una lib
                    target = filtered[1]
                    libs = " ".join(filtered[2:])
                    new_lines.append(f"target_link_libraries({target} {libs})\n")
                else:
                    # si solo queda target sin libs, omitimos la línea
                    pass

                found = True
            continue

        new_lines.append(line + "\n")

    cmake_path.write_text("".join(new_lines))

    if found:
        print(f"✅ {lib_name} removido del proyecto '{proyecto_name}'")
    else:
        print(f"❌ {lib_name} no se encontró en el proyecto")


def list_libs():
    """
Lista las librerías instaladas en LIB_PATH.
    """
    libs = [d for d in os.listdir(LIB_PATH) if os.path.isdir(os.path.join(LIB_PATH, d))]
    print("Librerías instaladas:")
    for l in libs:
        print(f" - {l}")


def list_pico_projects(): # tu función para cargar JSON
    """
Lista proyectos Pico encontrados en la ruta configurada.
Lista de nombres de carpetas de proyectos Pico válidos.
    """
    root = config.get("pico_projects_path")
    if not root or not os.path.exists(root):
        print("Ruta de proyectos Pico no encontrada.")
        return []

    # Solo carpetas que contengan CMakeLists.txt (convención de proyecto Pico)
    projects = [d for d in os.listdir(root)
                if os.path.isdir(os.path.join(root, d))
                and os.path.exists(os.path.join(root, d, "CMakeLists.txt"))]
    return projects


def initplab(proyecto_name):
    """
Inicializa la carpeta PicoLab dentro de un proyecto Pico.
proyecto_name Nombre del proyecto.
Crea wokwi.toml para integración con Wokwi.
    """
    proyecto_path = PP_PATH / proyecto_name
    if not proyecto_path.exists():  
        print(f"❌ Proyecto '{proyecto_name}' no encontrado en {PP_PATH}")
        return
    nombre_proyecto = proyecto_path.stem  # Nombre base del archivo .c o proyecto

    # Crear carpeta PicoLab
    picolab_path = proyecto_path / "PicoLab"
    picolab_path.mkdir(exist_ok=True)

    # Crear wokwi.toml con rutas relativas
    toml_path = picolab_path / "wokwi.toml"
    content = f"""[wokwi]
version = 1
firmware = '../build/{nombre_proyecto}.uf2'
elf = '../build/{nombre_proyecto}.elf'
"""
    with open(toml_path, "w") as f:
        f.write(content)
    print(f"Archivo wokwi.toml creado en {toml_path}")


def add_diagram_json(proyecto_name):
    """
Agrega un archivo diagram.json a la carpeta PicoLab de un proyecto.
proyecto_name Nombre del proyecto Pico.
Se abre un diálogo de selección de archivo usando Tkinter.
    """
    # Inicializar Tkinter (ocultamos la ventana principal)
    root = tk.Tk()
    root.withdraw()

    # Abrir explorador de archivos para seleccionar JSON
    archivo_json_path = filedialog.askopenfilename(
        title="Selecciona el archivo JSON",
        filetypes=[("Archivos JSON", "*.json")]
    )

    if not archivo_json_path:
        print("No se seleccionó ningún archivo")
        return

    archivo_json = Path(archivo_json_path).resolve()

    # Verificar que sea un JSON válido
    if archivo_json.suffix != ".json":
        print("Archivo no válido, debe ser un .json")
        return

    # Determinar carpeta PicoLab
    proyecto_path = PP_PATH / proyecto_name
    picolab_path = proyecto_path / "PicoLab"
    picolab_path.mkdir(exist_ok=True)

    # Copiar el archivo al proyecto
    destino = picolab_path / "diagram.json"
    shutil.copyfile(archivo_json, destino)
    print(f"Archivo JSON copiado a {destino}")


def turn_to_dev(proyecto_name, lib_name):
    """
Convierte un proyecto Pico a modo desarrollo para una librería.
proyecto_name Nombre del proyecto Pico.
lib_name Nombre de la librería.
Crea estructura include/src, archivos .h/.c base y modifica CMakeLists.txt.
    """
    proyecto_path = PP_PATH / proyecto_name
    if not proyecto_path.exists():  
        print(f"❌ Proyecto '{proyecto_name}' no encontrado en {PP_PATH}")
        return
    proyecto = Path(proyecto_path).resolve()
    lib_path = proyecto / "lib" / lib_name
    include_path = lib_path / "include"
    src_path = lib_path / "src"

    # Crear carpetas
    include_path.mkdir(parents=True, exist_ok=True)
    src_path.mkdir(parents=True, exist_ok=True)

    # Archivos base
    h_file = include_path / f"{lib_name}.h"
    c_file = src_path / f"{lib_name}.c"
    cmake_file = proyecto / "CMakeLists.txt"
    lib_cmake_file = lib_path / "CMakeLists.txt"

    # Normalizar nombre para guardas
    guard_name = f"{lib_name.upper()}_H"

    # Crear .h si no existe
    if not h_file.exists():
        h_file.write_text(
            f"#ifndef {guard_name}\n"
            f"#define {guard_name}\n\n"
            f"// Declaraciones de funciones de {lib_name}\n\n"
            f"#endif // {guard_name}\n"
        )

    # Crear .c si no existe
    if not c_file.exists():
        c_file.write_text(
            f'#include "{lib_name}.h"\n\n'
            f"// Definiciones de funciones de {lib_name}\n"
        )

    # Crear CMakeLists.txt dentro de la librería
    if not lib_cmake_file.exists():
        lib_cmake_file.write_text(
            f"add_library({lib_name} STATIC\n"
            f"    src/{lib_name}.c\n"
            f")\n\n"
            f"target_include_directories({lib_name} PUBLIC include)\n\n"
            f"target_link_libraries({lib_name} PUBLIC pico_stdlib)\n"
        )

    # Modificar CMakeLists principal
    if cmake_file.exists():
        cmake_content = cmake_file.read_text().splitlines()
        new_content = []
        target_name = None

        for line in cmake_content:
            if line.strip().startswith("add_executable("):
                # detectar nombre del target correctamente
                inside = line.strip()[len("add_executable("):].strip(" )")
                parts = inside.split()
                if parts:
                    target_name = parts[0]  # siempre el primer argumento es el target

                # meter el .c de la librería si no está
                if f"lib/src/{lib_name}.c" not in line and f"lib/{lib_name}/src/{lib_name}.c" not in line:
                    if line.endswith(")"):
                        line = line[:-1] + f"\n    lib/{lib_name}/src/{lib_name}.c)"
            new_content.append(line)

        # agregar target_include_directories si no existe
        include_line = f"    ${{CMAKE_CURRENT_LIST_DIR}}/lib/{lib_name}/include"
        cmake_joined = "\n".join(cmake_content)
        if target_name and include_line not in cmake_joined:
            new_content.append(
                f"\ntarget_include_directories({target_name} PRIVATE\n"
                f"    ${{CMAKE_CURRENT_LIST_DIR}}\n"
                f"{include_line}\n)"
            )
            
        cmake_file.write_text("\n".join(new_content) + "\n")


    print(f"✅ Proyecto convertido a modo desarrollo con lib '{lib_name}'")




def main():
    """
Función principal del script, interpreta comandos desde línea de comandos.
Comandos disponibles: install, add, turn2dev, remove, list, pplist, initplab, loadjson.
    """
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
            print("Uso: pmanager add <lib_name> <proyecto_path>")
        else:
            add_to_project(args[0], args[1])

    elif comando == "turn2dev":
        if len(args) != 2:
            print("Uso: pmanager turn2dev <proyecto_path> <lib_name>")
        else:
            turn_to_dev(args[0], args[1])

    elif comando == "remove":
        if len(args) != 2:
            print("Uso: pmanager remove <lib_name> <proyecto_path>")
        else:
            remove_from_project(args[0], args[1])

    elif comando == "list":
        list_libs()

    elif comando == "pplist":
        print("Proyectos Pico encontrados:")
        projects= list_pico_projects()
        for p in projects:
            print(f" - {p}")

    elif comando == "initplab":
        if len(args) != 1:
            print("Uso: pmanager initlab <proyecto_name>")
        else:
            print("Iniciando PicoLab...")
            initplab(args[0])

    elif comando == "loadjson":
        if len(args) != 1:
            print("Uso: pmanager loadjson <proyecto_name>")
        else:
            add_diagram_json(args[0])

    else:
        print(f"Comando desconocido: {comando}")


if __name__ == "__main__":
    main()