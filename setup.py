from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="machine_capacity_planner",
    version="1.0.0",
    description="Intelligent machine capacity selection engine for ERPNext v15+",
    author="YOUR_ORG",
    author_email="dev@yourorg.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
