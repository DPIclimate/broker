from questdb.ingress import Sender, IngressError, TimestampNanos
import sys
import random
import datetime
import requests

def insert_line_protocol(name: str, syms: str, cols: str, host: str = 'localhost', port: int = 9009) -> int:
    try:
        with Sender(host, port) as sender:
            sender.row(
                    name,
                    symbols=syms,
                    columns=cols,
                    at=TimestampNanos.now())

            sender.flush()

    except IngressError as e:
        sys.stderr.write(f'error: {e}\n')


def get_http_query(query: str, host: str = 'localhost', port: int = 9000) -> str:
    return requests.get(
        f'http://{host}:{port}/exec',
        {
            'query': query
        })

def get_last_insert(table: str, host: str = 'localhost', port: int = 9000) -> str:
    return requests.get(
        f'http://{host}:{port}/exp',
        {
            'query':f'SELECT * FROM {table} LIMIT -1'
        }).text

if __name__ == "__main__":
    insert_line_protocol('test',{'device':'001', 'type':'speaker'}, {'volume':random.uniform(0,1)})
    print(get_http_query('SELECT * FROM test LIMIT -1').text)

