from setuptools import setup, find_packages

setup(
    name="pmanager",
    version="0.1.3",
    packages=find_packages(),
    include_package_data=True,  # <- permite incluir archivos extras
    entry_points={
        "console_scripts": [
            "pmanager=pmanager.pmanager:main",
        ],
    },
)