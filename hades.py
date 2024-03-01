#!/usr/bin/python3
import os
import argparse
from time import perf_counter
from functools import cache
from rich import print
from elevate import elevate
import asyncio

from hadespm.repo.sisyphus import Sisyphus


def is_root():
	return os.getuid() == 0


@cache
async def main() -> None:
	if not is_root():
		elevate(graphical=False)

	print('HadesPM: пакетный менеджер на базе RPM для Alt Sisyphus')
	program_start = perf_counter()
	sisyphus = Sisyphus()

	parser = argparse.ArgumentParser(description='Быстрый пакетный менеджер для Alt Sisyphus')
	parser.add_argument("--update", '-u', action="store_true", help='Обновить список пакетов')
	parser.add_argument("--search", '-s', action="store_true", help='Искать пакет по названию')
	parser.add_argument("--install", '-i', action="store_true", help='Обновить список пакетов')
	parser.add_argument("--pkg", '-p', type=str, help='Имя пакета/пакетов')

	args = parser.parse_args()

	if args.update:
		task = asyncio.create_task(sisyphus.read_packages_list())
	elif args.install:
		if args.pkg:
			task = asyncio.create_task(sisyphus.install_package(args.pkg))
		else:
			print('[red]Ошибка: [/red] вы не ввели названия пакетов для установки')
	elif args.search:
		if args.pkg:
			task = asyncio.create_task(sisyphus.search_package(args.pkg))
		else:
			print('[red]Ошибка: [/red] вы не ввели названия пакетов для установки')
	else:
		print('[red]Ошибка: [/red] не было введено аргументов. `--help` или `-h` для просмотра справки')

	await task

	program_end = perf_counter()
	work_time = round(program_end - program_start, 4)
	print(f'Время работы: {work_time} сек.')


if __name__ == '__main__':
	asyncio.run(main())
