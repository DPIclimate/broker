#!/usr/local/bin/python

import argparse, datetime, json, sys
from re import U
from typing import Dict, List
import api.client.DAO as dao
from pdmodels.Models import LogicalDevice, PhysicalDevice, PhysicalToLogicalMapping
from pydantic import BaseModel
import os
import hashlib

def str_to_physical_device(val) -> PhysicalDevice:
    return PhysicalDevice.parse_obj(json.loads(val))

def str_to_logical_device(val) -> LogicalDevice:
    return LogicalDevice.parse_obj(json.loads(val))

def str_to_dict(val) -> Dict:
    return json.loads(val)

main_parser = argparse.ArgumentParser()
main_sub_parsers = main_parser.add_subparsers(dest='cmd1')

# Physical device commands
pd_parser = main_sub_parsers.add_parser('pd', help='physical device operations')
pd_sub_parsers = pd_parser.add_subparsers(dest='cmd2')

## Get physical device
pd_get_parser = pd_sub_parsers.add_parser('get', help='get physical device')
pd_get_parser.add_argument('--puid', type=int, help='physical device uid', dest='p_uid', required=True)
pd_get_parser.add_argument('--properties', action='store_true', help='Include the properties field in the output', dest='include_props', required=False)

## List unmapped physical devices
pd_lum_parser = pd_sub_parsers.add_parser('lum', help='list unmapped physical devices')
pd_lum_parser.add_argument('--source', help='Physical device source name', dest='source_name')
pd_lum_parser.add_argument('--plain', action='store_true', help='Plain output, not JSON', dest='plain')
pd_lum_parser.add_argument('--properties', action='store_true', help='Include the properties field in the output', dest='include_props', required=False)

## List physical devices
pd_ls_parser = pd_sub_parsers.add_parser('ls', help='list physical devices')
pd_ls_parser.add_argument('--source', help='Physical device source name', dest='source_name')
pd_ls_parser.add_argument('--plain', action='store_true', help='Plain output, not JSON', dest='plain')
pd_ls_parser.add_argument('--properties', action='store_true', help='Include the properties field in the output', dest='include_props', required=False)

## Create physical device
pd_mk_parser = pd_sub_parsers.add_parser('create', help='create physical devices')
group = pd_mk_parser.add_mutually_exclusive_group(required=True)
group.add_argument('--json', type=str_to_dict, help='Physical device JSON', dest='pd')
group.add_argument('--file', help='Read json from file, - for stdin', dest='in_filename')

## Update physical device
pd_up_parser = pd_sub_parsers.add_parser('up', help='update physical devices')
pd_up_parser.add_argument('--puid', type=int, help='Physical device uid', dest='p_uid', required=True)
group = pd_up_parser.add_mutually_exclusive_group(required=True)
group.add_argument('--json', type=str_to_dict, help='Physical device JSON', dest='pd')
group.add_argument('--file', help='Read json from file, - for stdin', dest='in_filename')

## Delete physical devices
pd_rm_parser = pd_sub_parsers.add_parser('rm', help='delete physical devices')
pd_rm_parser.add_argument('--puid', type=int, help='physical device uid', dest='p_uid', required=True)


# Logical device commands
ld_parser = main_sub_parsers.add_parser('ld', help='logical device operations')
ld_sub_parsers = ld_parser.add_subparsers(dest='cmd2')

## List logical devices
ld_ls_parser = ld_sub_parsers.add_parser('ls', help='list logical devices')
ld_ls_parser.add_argument('--plain', action='store_true', help='Plain output, not JSON', dest='plain')

## Create logical devices
ld_mk_parser = ld_sub_parsers.add_parser('create', help='create logical device')
group = ld_mk_parser.add_mutually_exclusive_group(required=True)
group.add_argument('--json', type=str_to_dict, help='Physical device JSON', dest='pd')
group.add_argument('--file', help='Read json from file, - for stdin', dest='in_filename')

## Get logical device
ld_get_parser = ld_sub_parsers.add_parser('get', help='get logical device')
ld_get_parser.add_argument('--luid', type=int, help='logical device uid', dest='l_uid', required=True)
ld_get_parser.add_argument('--properties', action='store_true', help='Include the properties field in the output', dest='include_props', required=False)

## Update logical devices
ld_up_parser = ld_sub_parsers.add_parser('up', help='update logical device')
ld_up_parser.add_argument('--luid', type=int, help='logical device uid', dest='l_uid', required=True)
group = ld_up_parser.add_mutually_exclusive_group(required=True)
group.add_argument('--json', type=str_to_dict, help='Physical device JSON', dest='pd')
group.add_argument('--file', help='Read json from file, - for stdin', dest='in_filename')

## Delete logical devices
ld_rm_parser = ld_sub_parsers.add_parser('rm', help='delete logical devices')
ld_rm_parser.add_argument('--luid', type=int, help='logical device uid', dest='l_uid', required=True)

## Copy physical device to new logical device
ld_cpd_parser = ld_sub_parsers.add_parser('cpd', help='copy physical device to logical device')
ld_cpd_parser.add_argument('--puid', type=int, help='Physical device uid', dest='p_uid')
ld_cpd_parser.add_argument('--map', action='store_true', help='Create mapping', dest='do_mapping')


# Device mapping commands
map_parser = main_sub_parsers.add_parser('map', help='mapping operations')
map_sub_parsers = map_parser.add_subparsers(dest='cmd2')

## Map physical device to logical device
map_start_parser = map_sub_parsers.add_parser('start', help='start mapping from physical device to logical device')
map_start_parser.add_argument('--puid', type=int, help='Physical device uid', dest='p_uid', required=True)
map_start_parser.add_argument('--luid', type=int, help='Logical device uid', dest='l_uid', required=True)

## List mapping
map_ls_parser = map_sub_parsers.add_parser('ls', help='list mapping for device')
group = map_ls_parser.add_mutually_exclusive_group(required=True)
group.add_argument('--puid', type=int, help='Physical device uid', dest='p_uid')
group.add_argument('--luid', type=int, help='Logical device uid', dest='l_uid')

## End mapping
map_end_parser = map_sub_parsers.add_parser('end', help='end mapping from physical device to logical device')
group = map_end_parser.add_mutually_exclusive_group(required=True)
group.add_argument('--puid', type=int, help='Physical device uid', dest='p_uid')
group.add_argument('--luid', type=int, help='Logical device uid', dest='l_uid')


#User commands
user_parser=main_sub_parsers.add_parser('users', help="manage users")
user_sub_parsers=user_parser.add_subparsers(dest='cmd2')

#Add user
user_add_parser=user_sub_parsers.add_parser('add', help="Add a user")
user_add_parser.add_argument('-u', help="Username of user", dest='uname', required=True)
user_add_parser.add_argument('-p', help="Password for user", dest='passwd', required=True)
user_add_parser.add_argument('-d', help="Account is disable upon creation", action='store_true', dest='disabled')

#Remove user
user_rm_parser=user_sub_parsers.add_parser('rm', help="Remove a user")
user_rm_parser.add_argument('-u', help="Username of user to be removed", dest='uname', required=True)

#Manage users token
user_token_parser=user_sub_parsers.add_parser('token', help="Manage a user's token")
user_token_parser.add_argument('-u', help="Username", dest='uname', required=True)
user_token_parser.add_argument('--refresh', help="Refresh a users token", action='store_true')

group=user_token_parser.add_mutually_exclusive_group()
group.add_argument('--disable', help="Disable a users token", action="store_true")
group.add_argument('--enable', help="Enable a users token", action='store_true')

#Change users password
user_pw_change_passer=user_sub_parsers.add_parser('chng', help="Change a user's password")
user_pw_change_passer.add_argument('-u', help="Username", dest='uname', required=True)
user_pw_change_passer.add_argument('-p', help="New password for user", dest='passwd')

#List users
user_sub_parsers.add_parser('ls', help="List all users")

args = main_parser.parse_args()

def serialise_datetime(obj):
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    print(f'Cannot serialise {type(obj)}, {obj}')
    return "NO CONVERSION"


def now() -> datetime.datetime:
        return datetime.datetime.now(tz=datetime.timezone.utc)


def pretty_print_json(object: List | Dict | BaseModel) -> str:
    x = object.dict() if isinstance(object, BaseModel) else object
    if isinstance(x, dict):
        if hasattr(args, 'include_props') and not args.include_props:
            x.pop("properties")

    return json.dumps(x, indent=2, default=serialise_datetime)


def get_last_seen(d: PhysicalDevice | LogicalDevice) -> str:
#                    2022-04-14T13:52+10:00    
    log_last_seen = 'Never                 '
    if d.last_seen is not None:
        log_last_seen = d.last_seen.isoformat(timespec="minutes")

    return log_last_seen


def plain_pd_list(devs: List[PhysicalDevice]):
    for d in devs:
        m = dao.get_current_device_mapping(pd=d.uid)
        print(f'{d.uid: >5}   {d.name: <48}   {get_last_seen(d)}', end='')
        if m is not None:
            l = m.ld
            if l is not None:
                print(f' --> {l.uid: >5}   {l.name: <48}   {get_last_seen(l)}', end='')

        print()


def dict_from_file_or_string() -> dict:
    if args.pd is not None and args.in_filename is not None:
        raise RuntimeError('error: --json and --file are mutually exclusive.')

    json_obj = None
    if args.in_filename is not None:
        if args.in_filename == '-':
            json_obj = json.load(sys.stdin)
        else:
            with open(args.in_filename) as jf:
                json_obj = json.load(jf)

    elif args.pd is not None:
        json_obj = args.pd

    if json_obj is None:
        raise RuntimeError('No physical device object given via either --json or --file.')

    return json_obj

def main() -> None:
    if args.cmd1 == 'pd':
        if args.cmd2 == 'ls':
            if args.source_name is None:
                devs = dao.get_physical_devices()
            else:
                devs = dao.get_physical_devices({'source': args.source_name})

            if not args.plain:
                if args.include_props:
                    tmp_list = list(map(lambda dev: dev.dict(), devs))
                else:
                    tmp_list = list(map(lambda dev: dev.dict(exclude={'properties'}), devs))

                print(pretty_print_json(tmp_list))
            else:
                plain_pd_list(devs)
        elif args.cmd2 == 'get':
            dev = dao.get_physical_device(args.p_uid)
            print(pretty_print_json(dev))
        elif args.cmd2 == 'lum':
            devs = dao.get_unmapped_physical_devices()
            if args.source_name is not None:
                devs = list(filter(lambda d: d.dict()['source_name'] == args.source_name, devs))
            if not args.plain:
                if args.include_props:
                    tmp_list = list(map(lambda dev: dev.dict(), devs))
                else:
                    tmp_list = list(map(lambda dev: dev.dict(exclude={'properties'}), devs))

                print(pretty_print_json(tmp_list))
            else:
                plain_pd_list(devs)

        elif args.cmd2 == 'create':
            dev = PhysicalDevice.parse_obj(dict_from_file_or_string())
            print(pretty_print_json(dao.create_physical_device(dev)))

        elif args.cmd2 == 'up':
            json_obj = dict_from_file_or_string()
            dev = dao.get_physical_device(args.p_uid)
            if dev is None:
                raise RuntimeError('Physical device not found.')

            dev = dev.dict()
            for k, v in json_obj.items():
                if k == "uid":
                    continue
                if dev[k] != v:
                    dev[k] = v

            dev = PhysicalDevice.parse_obj(dev)
            print(pretty_print_json(dao.update_physical_device(dev)))
        elif args.cmd2 == 'rm':
            print(pretty_print_json(dao.delete_physical_device(args.p_uid)))
    elif args.cmd1 == 'ld':
        if args.cmd2 == 'ls':
            devs = dao.get_logical_devices()
            tmp_list = list(map(lambda dev: dev.dict(exclude={'properties'}), devs))
            if not args.plain:
                print(pretty_print_json(tmp_list))
            else:
                plain_pd_list(devs)
        elif args.cmd2 == 'create':
            dev = LogicalDevice.parse_obj(dict_from_file_or_string())
            print(dao.create_logical_device(dev))
        elif args.cmd2 == 'get':
            dev = dao.get_logical_device(args.l_uid)
            print(pretty_print_json(dev))
        elif args.cmd2 == 'up' and args.ld is not None:
            json_obj = dict_from_file_or_string()
            dev = dao.get_logical_device(args.l_uid)
            if dev is None:
                raise RuntimeError('Logical device not found.')

            for k, v in json_obj.items():
                if k == "uid":
                    continue
                if dev[k] != v:
                    dev[k] = v

            dev = LogicalDevice.parse_obj(dev)
            print(pretty_print_json(dao.update_logical_device(dev)))
        elif args.cmd2 == 'rm':
            print(dao.delete_logical_device(args.l_uid))
        elif args.cmd2 == 'cpd':
            pdev = dao.get_physical_device(args.p_uid)
            if pdev is None:
                raise RuntimeError('Physical device not found.')

            ldev = LogicalDevice.parse_obj(pdev.dict(exclude={'uid','source_name','source_ids','properties'}))
            ldev = dao.create_logical_device(ldev)
            if args.do_mapping:
                mapping = PhysicalToLogicalMapping(pd=pdev, ld=ldev, start_time=now())
                dao.insert_mapping(mapping)
                mapping = dao.get_current_device_mapping(ld=ldev.uid)
                print(pretty_print_json(mapping))
    elif args.cmd1 == 'map':
        if args.cmd2 == 'start':
            pdev = dao.get_physical_device(args.p_uid)
            if pdev is None:
                raise RuntimeError('Physical device not found.')
            ldev = dao.get_logical_device(args.l_uid)
            if ldev is None:
                raise RuntimeError('Logical device not found.')
            mapping = PhysicalToLogicalMapping(pd=pdev, ld=ldev, start_time=now())
            dao.insert_mapping(mapping)
            mapping = dao.get_current_device_mapping(ld=ldev.uid)
            print(json.dumps(mapping.dict(), indent=2, default=serialise_datetime))
        elif args.cmd2 == 'end':
            if args.p_uid is not None:
                dao.end_mapping(pd=args.p_uid)
            else:
                dao.end_mapping(ld=args.l_uid)
        elif args.cmd2 == 'ls':
            if args.p_uid is not None:
                mapping = dao.get_current_device_mapping(pd=args.p_uid)
                print(pretty_print_json(mapping))
            elif args.l_uid is not None:
                map_list = dao.get_logical_device_mappings(args.l_uid)
                new_list = [m.dict() for m in map_list]
                print(pretty_print_json(new_list))
    
    elif args.cmd1=='users':
        if args.cmd2=='add':
            dao.user_add(uname=args.uname, passwd=args.passwd, disabled=args.disabled)

        elif args.cmd2=='rm':
            dao.user_rm(uname=args.uname)

        elif args.cmd2=='token':
            if args.disable==True:
                dao.token_disable(uname=args.uname)

            elif args.enable==True:
                dao.token_enable(uname=args.uname)
            
            if args.refresh==True:
                dao.token_refresh(uname=args.uname)

        elif args.cmd2=='chng':
            dao.user_change_password(args.uname, args.passwd)
        
        elif args.cmd2=='ls':
            print(dao.user_ls())

if __name__ == '__main__':
    main()
