"""
Hermes Agent via Mammouth AI - Installation Python

Usage :
    pip install -e .
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="hermes-mammouth",
    version="1.0.0",
    author="Francois Salazar",
    description="Assistant personnel basé sur Hermes 3 via l'API Mammouth AI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=[
        "mistralai>=1.0.0",  # SDK OpenAI-compatible pour Mammouth AI
        "python-dotenv>=1.0.0",  # Gestion des variables d'environnement
        "rich>=13.0.0",  # Affichage coloré en terminal
    ],
    extras_require={
        "api": [
            "flask>=3.0.0",  # Pour l'API web
        ],
    },
)
