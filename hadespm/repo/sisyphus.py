#!/usr/bin/python3
import re
import sys
import subprocess
from functools import cache
from rich.tree import Tree
from rich import print
from tqdm.asyncio import tqdm
import aiohttp
import httpx
from elevate import elevate
from bs4 import BeautifulSoup
import asyncio
import rpmfile


@cache
def get_size(bytes, suffix='Б'):
	factor = 1024
	for unit in ["", "К", "М", "Г", "Т", "П"]:
		if bytes < factor:
			return f'{bytes:.2f}{unit}{suffix}'
		bytes /= factor


class Sisyphus:
	def __init__(self, arch: str="x86_64", pkg_type: str="RPMS.classic"):
		self.arch = arch
		self.pkg_type = pkg_type
		self.url = f"http://ftp.altlinux.org/pub/distributions/ALTLinux/Sisyphus/{self.arch}/{self.pkg_type}"
		self.packages_list = []

	@cache
	async def read_packages_list(self) -> list:
		try:
			async with aiohttp.ClientSession() as session:
				async with session.get(self.url) as resp:
					text = await resp.read()
					bs4 = BeautifulSoup(text.decode('utf-8'), 'lxml')

					async for package in tqdm(bs4.findAll('a'), desc='Обновление списка пакетов', ascii=False, 
											unit='пакет', smoothing=0.5, colour='yellow', 
											bar_format='{desc}: {percentage:3.0f}%| {bar} | {n_fmt}/{total_fmt} {rate_fmt}{postfix}'):
						self.packages_list.append(package.text)

			return self.packages_list
		except aiohttp.client_exceptions.ClientConnectorError:
			print('[red]Ошибка подключения к зеркалу пакетов (проверьте соединение с интернетом)[/red]')
			sys.exit()

	@cache
	async def read_package(self, package_path: str) -> None:
		with rpmfile.open(package_path) as rpm:
			arch = rpm.headers.get('arch', 'noarch').decode()
			name = rpm.headers.get('name').decode()
			description = rpm.headers.get('description').decode()
			size = rpm.headers.get('size')
			version = rpm.headers.get('version').decode()
			summary = rpm.headers.get('summary').decode()
			archivesize = rpm.headers.get('archivesize')
			group = rpm.headers.get('group', 'нет группы').decode()
			print(f'''
Информация о пакете {name} v{version} ({group}):
Архитектура: {arch}
Краткое описание: {summary}
Описание: {description}
Размер пакета: {get_size(size)}
Размер архива: {get_size(archivesize)}''')

			install_accept = input(f'Установить пакет {name}? (y/n) ').lower()

			if install_accept[0] == 'n' or install_accept[0] == 'н':
				print('[red]Установка прервана[/red]')
				sys.exit()
			else:
				command = ['rpm', '-qp', '--requires', package_path]
				result = subprocess.run(command, capture_output=True, text=True)   
				deps = result.stdout.split("\n")
				deps = [dependency.strip() for dependency in deps if dependency.strip()]
				dependencies = []

				if result.returncode == 0: 
					for dependency in deps:
						print(dependency)
					command = ["rpm2cpio" ,package_path, "|", "cpio", "-i", "-d", ">>", "/dev/null"]
					subprocess.run(command)
					print(f"[green]Пакет {name} успешно установлен[/green]")

	@cache
	async def download_package(self, package_name: str) -> None:
		elevate()
		filepath = f'/tmp/{package_name}'
		with open(filepath, 'wb') as file:
			async with httpx.AsyncClient() as client:
				async with client.stream('GET', f'{self.url}/{package_name}') as stream:
					stream.raise_for_status()
					total = int(stream.headers.get('content-length', 0))
					print(f'Получение {package_name} ({get_size(total)})')

					with tqdm(total=total, desc=f'Скачивание {package_name}', ascii=False, 
								unit='пакет', smoothing=0.5, colour='yellow', 
								bar_format='{desc}: {percentage:3.0f}%| {bar} | {n_fmt}/{total_fmt} {rate_fmt}{postfix}') as pb:
						async for chunk in stream.aiter_bytes():
							pb.update(len(chunk))
							file.write(chunk)

		task_read_pkg = asyncio.create_task(self.read_package(filepath))
		await task_read_pkg

	@cache
	async def search_package(self, package: str):
		task = asyncio.create_task(self.read_packages_list())
		await task

		finded_packages = []
		packages_candidates = []
		async for pkg_in_repo in tqdm(self.packages_list, desc='Поиск пакета', ascii=False, 
								unit='пакет', smoothing=0.5, colour='yellow', 
								bar_format='{desc}: {percentage:3.0f}%| {bar} | {n_fmt}/{total_fmt} {rate_fmt}{postfix}'):
			if package.lower() in pkg_in_repo.lower():
				finded_packages.append(pkg_in_repo)

		if len(finded_packages) > 0:
			packages_tree = Tree(f"[green]Кандидаты пакета {package}")

			for pkg_num, finded_package in enumerate(finded_packages):
				pattern = r'-alt\d+[-\d]*'
				pkg_name = finded_package.replace('.x86_64.rpm', '').replace(re.findall(pattern, finded_package)[0], '')
				packages_tree.add(f"[cyan][{pkg_num}] {pkg_name}")
				packages_candidates.append(finded_package)

			print(packages_tree)
		else:
			print('[red]Пакетов не найдено[/red]')

	@cache
	async def install_package(self, package: list) -> None:
		task = asyncio.create_task(self.read_packages_list())
		await task

		finded_packages = []
		packages_candidates = []

		async for pkg_in_repo in tqdm(self.packages_list, desc='Поиск пакета', ascii=False, 
								unit='пакет', smoothing=0.5, colour='yellow', 
								bar_format='{desc}: {percentage:3.0f}%| {bar} | {n_fmt}/{total_fmt} {rate_fmt}{postfix}'):
			if package.lower() in pkg_in_repo.lower():
				finded_packages.append(pkg_in_repo)

		if len(finded_packages) > 0:
			packages_tree = Tree(f"[green]Кандидаты пакета {package}")

			for pkg_num, finded_package in enumerate(finded_packages):
				pattern = r'-alt\d+[-\d]*'
				pkg_name = finded_package.replace('.x86_64.rpm', '').replace(re.findall(pattern, finded_package)[0], '')
				packages_tree.add(f"[cyan][{pkg_num}] {pkg_name}")
				packages_candidates.append(finded_package)

			print(packages_tree)

			if len(packages_candidates) > 1:
				pkg_num = input('Введите номер пакета-кандидата: ')

				if pkg_num.isdigit():
					pkg_num = int(pkg_num)
					if pkg_num <= len(packages_candidates):
						download_task = asyncio.create_task(self.download_package(packages_candidates[pkg_num]))
						await asyncio.gather(download_task)
					else:
						print(f'[red]Пакет-кандидат с номером {pkg_num} не найден[/red]')
						sys.exit()
				else:
					print('[red]Вы ввели не номер[/red]')
					sys.exit()
			else:
				print(f'[green]Установка {packages_candidates[0]}[/green]')
				task = asyncio.create_task(self.download_package(packages_candidates[0]))
				await task
		else:
			print(f'[red]Пакетов с названием {package} не найдено[/red]')
