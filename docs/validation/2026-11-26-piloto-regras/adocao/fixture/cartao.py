"""Demonstração histórica do mural. Entradas: dia consultado, último dia."""
import sys

if __name__ == '__main__':
    hoje, ultimo = map(int, sys.argv[1:])
    print('visível' if hoje < ultimo else 'oculto')
