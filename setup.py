# -*- coding: utf-8 -*-
"""
QuickDraw-Screenshot セットアップスクリプト
超軽量・高速スクリーンショットツール
"""

from setuptools import setup, find_packages
from src.__version__ import __version__, __author__, __email__, __description__

# 依存関係を読み込む
with open('requirements.txt', 'r', encoding='utf-8') as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

# READMEを読み込む
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='quickdraw-screenshot',
    version=__version__,
    author=__author__,
    author_email=__email__,
    description=__description__,
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/pavel/QuickDraw-Screenshot',
    packages=find_packages(),
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: End Users/Desktop',
        'Topic :: Multimedia :: Graphics :: Capture :: Screen Capture',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Operating System :: Microsoft :: Windows',
        'Natural Language :: Japanese',
    ],
    keywords='screenshot, screen capture, lightweight, windows, 軽量, スクリーンショット',
    python_requires='>=3.8',
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'quickdraw=main:main',
        ],
    },
    project_urls={
        'Bug Reports': 'https://github.com/pavel/QuickDraw-Screenshot/issues',
        'Source': 'https://github.com/pavel/QuickDraw-Screenshot',
    },
)