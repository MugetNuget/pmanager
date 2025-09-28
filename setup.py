from setuptools import setup, find_packages

setup(
    name="pmanager",
    version="0.2.1",
    packages=find_packages(),
    include_package_data=True,  # <- permite incluir archivos extras
    entry_points={
        "console_scripts": [
            "pmanager=pmanager.pmanager:main",
        ],
    },

)
