import os
import re
import tempfile
import subprocess
from contextlib import contextmanager
from typing import List, Dict


class LeanGymConnection:
    '''
    A class that allows to communicate with a lean-gym REPL interface through Python.
    Each time the instance of this class is created, it invokes a new screen detached session with a lean script running in it.
    Use 'init_search', 'run_tactic' and 'clear_search' methods to send commands and 'collect' method to gather results.
    '''

    __n_conns = 0

    def __init__(self, path: str):
        '''
        :param path: a path to the lean-gym root folder.
        :raises OSError: if lean or screen are not found
        '''

        LeanGymConnection.__n_conns += 1
        self.__closed = False

        self.__filename = tempfile.NamedTemporaryFile(delete=False).name
        self.__file = open(self.__filename, 'r')

        screen = f'lean_repl{LeanGymConnection.__n_conns}'
        self.__START = f'screen -Logfile {self.__filename} -dmSL {screen} lean --run src/repl.lean'.split(' ')
        self.__QUERY = f'screen -S {screen} -X stuff'.split(' ')
        self.__EXIT  = f'screen -S {screen} -X quit'.split(' ')

        # TODO: check if lean exists
        try:
            subprocess.run(self.__START, cwd=path)
        except FileNotFoundError as e:
            raise OSError('screen (terminal command) is not found')
        # TODO: check if screen session created

        self.__queries = 0

    def __send_query(self, cmd: list):
        cmd = str(cmd).replace("'", '"')
        subprocess.run(self.__QUERY + [f'{cmd}\n'])

    def init_search(self, name: str, namespaces: List[str] = []):
        '''
        Sends 'init_search' command to the lean-gym.
        :param name: a declaration name to search
        :param namespaces: a list of open namespaces
        :raises ValueError: if connection is closed
        '''

        if self.__closed:
            raise ValueError('connection is closed')

        self.__queries += 1
        self.__send_query(['init_search', [name, '']])

    def run_tac(self, search_id: int, tactic_state_id: int, tactic: str):
        '''
        Sends 'run_tac' command to the lean-gym.
        :param tactic: a tactic to apply
        :param search_id: an id of a search state
        :param tactic_state_id: an id of a tactic state
        :raises ValueError: if connection is closed
        '''

        if self.__closed:
            raise ValueError('connection is closed')

        self.__queries += 1
        tactic = tactic.replace('\n', '\\n')
        self.__send_query(['run_tac', [str(search_id), str(tactic_state_id), tactic]])

    def clear_search(self, search_id: int):
        '''
        Sends 'clear_search' command to the lean-gym.
        :param search_id: an id of a search state
        :raises ValueError: if connection is closed
        '''

        if self.__closed:
            raise ValueError('connection is closed')

        self.__queries += 1
        self.__send_query(['clear_search', [str(search_id)]])

    def collect(self) -> List[Dict]:
        '''
        Waits until all results of currently executing commands are ready and returns them.
        :returns: list of results as dictionaries
        :raises ValueError: if connection is closed
        '''
       
        if self.__closed:
            raise ValueError('connection is closed')

        result = []
        while self.__queries > 0:
            line = self.__file.readline()
            if line == '':
                continue
            elif line[0] == '{':
                result.append(self.__parse_response(line))
                self.__queries -= 1
        return result

    def __parse_response(self, responce: str):
        result = {}

        for key, value in re.findall(r'"([_\w]+)":(null|\[[^\[\]]*\]|"[^"]*")', responce):
            if value == 'null':
                result[key] = None
            elif re.match(r'"[0-9]+"', value):
                result[key] = int(value[1:-1])
            elif value[0] == '"':
                result[key] = value[1:-1].replace('\\n', '\n')
            else:
                result[key] = re.findall(r'"([^"]*)"', value)

        return result 

    def close(self):
        '''
        Releases all resources.
        :raises ValueError: if connection is closed
        '''

        if self.__closed:
            raise ValueError('connection is closed')
        self.__closed = True

        subprocess.run(self.__EXIT)
        self.__file.close()
        os.remove(self.__filename)


@contextmanager
def invoke_lean(*args, **kwds):
    '''
    A context manager that creates an instance of LeanGymConnection. 
    '''

    connection = LeanGymConnection(*args, **kwds)
    try:
        yield connection
    finally:
        connection.close()
