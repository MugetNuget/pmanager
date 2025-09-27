pmanager es un gestor de librerías Python personal que facilita la instalación y actualización de tus librerías locales de forma centralizada. Permite mantener tus librerías organizadas y disponibles para múltiples proyectos en tu máquina.

Características

Instala y actualiza librerías locales desde repositorios Git.

Soporta librerías en C para tus proyectos usando VS Code con la extension RaspBerry Pi Pico, organizadas en una carpeta central.

Permite configurar la ubicación de tus librerías mediante un archivo JSON.

Integración sencilla con cualquier proyecto Pi Pico.

Instalacion

puedes utilizar directamente pip para instalar el gestor, por ahora no se encuentra publicado en pypi.

pip install git+https://github.com/MugetNuget/pmanager.git

actualiza con pip install --upgrade git+https://github.com/MugetNuget/pmanager.git

Configuracion

Puedes cambiar la ruta de descarga de las librerías locales y la ruta de tus proyectos en c para pi pico utilizando el archivo pmanager_config
con el siguiente formato:

{
 "pico_projects_path": "C:/Users/user/PicoProjects",
 "lib_path": "C:/Users/user/.pclibs"
}