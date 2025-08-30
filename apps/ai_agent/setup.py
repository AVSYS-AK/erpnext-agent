from setuptools import setup, find_packages
setup(
    name="ai_agent",
    version="0.1.0",
    description="Agentic AI for Frappe/ERPNext",
    author="Proxta",
    author_email="eng@proxta.in",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
)
