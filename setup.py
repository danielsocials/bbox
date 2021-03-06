from distutils.core import setup
from setuptools import find_packages

setup(name='aiobbox',
      version='0.1.4',
      description='multi-lang, highly available rpc framework',
      author='Zeng Ke',
      author_email='zk@bixin.com',
      packages=find_packages(),
      scripts=['bin/bbox', 'bin/bbox.py', 'bin/bbox-gencert'],
      install_requires=[
          'aiohttp',
          'aiochannel',
          'websockets',
          'aio_etcd',
          'netifaces'
      ]
)
