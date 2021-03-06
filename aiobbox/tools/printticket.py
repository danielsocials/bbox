import os, sys
import json
import argparse
from aiobbox.cluster import get_ticket
from aiobbox.handler import BaseHandler

class Handler(BaseHandler):
    help = 'print ticket info'
    def add_arguments(self, parser):
        parser.add_argument(
            'key',
            type=str,
            help='print key')

    async def run(self, args):
        print(get_ticket()[args.key])
