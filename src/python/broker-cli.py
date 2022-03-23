import argparse, datetime, json
from typing import Dict, List
import api.client.DAO as dao
from pdmodels.Models import LogicalDevice, PhysicalDevice, PhysicalToLogicalMapping
from pydantic import BaseModel

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

## List unmapped physical devices
pd_lum_parser = pd_sub_parsers.add_parser('lum', help='list unmapped physical devices')

## List unmapped physical devices
pd_ls_parser = pd_sub_parsers.add_parser('ls', help='list physical devices')
pd_ls_parser.add_argument('--source', help='Physical device source name', dest='source_name')

## Create physical device
pd_mk_parser = pd_sub_parsers.add_parser('create', help='create physical devices')
pd_mk_parser.add_argument('--json', type=str_to_physical_device, help='Physical device JSON', dest='pd', required=True)

## Update physical device
pd_up_parser = pd_sub_parsers.add_parser('up', help='update physical devices')
pd_up_parser.add_argument('--puid', type=int, help='Physical device uid', dest='p_uid')
pd_up_parser.add_argument('--json', type=str_to_dict, help='Physical device JSON', dest='pd', required=True)

## Delete physical devices
pd_rm_parser = pd_sub_parsers.add_parser('rm', help='delete physical devices')
pd_rm_parser.add_argument('--puid', type=int, help='physical device uid', dest='p_uid', required=True)


# Logical device commands
ld_parser = main_sub_parsers.add_parser('ld', help='logical device operations')
ld_sub_parsers = ld_parser.add_subparsers(dest='cmd2')

## List logical devices
ld_ls_parser = ld_sub_parsers.add_parser('ls', help='list logical devices')

## Create logical devices
ld_mk_parser = ld_sub_parsers.add_parser('create', help='create logical device')
ld_mk_parser.add_argument('--json', type=str_to_logical_device, help='Logical device JSON', dest='ld', required=True)

## Update logical devices
ld_up_parser = ld_sub_parsers.add_parser('up', help='update logical device')
ld_up_parser.add_argument('--luid', type=int, help='logical device uid', dest='l_uid', required=True)
ld_up_parser.add_argument('--json', type=str_to_dict, help='Logical device JSON', dest='ld', required=True)

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
map_start_parser.add_argument('--puid', type=int, help='Physical device uid', dest='p_uid')
map_start_parser.add_argument('--luid', type=int, help='Logical device uid', dest='l_uid')

## List mapping
map_ls_parser = map_sub_parsers.add_parser('ls', help='list mapping for device')
map_ls_parser.add_argument('--puid', type=int, help='Physical device uid', dest='p_uid')
map_ls_parser.add_argument('--luid', type=int, help='Logical device uid', dest='l_uid')

## End mapping
map_end_parser = map_sub_parsers.add_parser('end', help='end mapping from physical device to logical device')
map_end_parser.add_argument('--luid', type=int, help='Logical device uid', dest='l_uid')

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
    return json.dumps(x, indent=2, default=serialise_datetime)

def main() -> None:
    if args.cmd1 == 'pd':
        if args.cmd2 == 'ls':
            if args.source_name is None:
                devs = dao.get_physical_devices()
            else:
                devs = dao.get_physical_devices({'source': args.source_name})
            tmp_list = list(map(lambda dev: dev.dict(exclude={'properties'}), devs))
            print(pretty_print_json(tmp_list))
        elif args.cmd2 == 'lum':
            unmapped_devices = dao.get_unmapped_physical_devices()
            tmp_list = list(map(lambda dev: dev.dict(exclude={'properties'}), unmapped_devices))
            print(pretty_print_json(tmp_list))
        elif args.cmd2 == 'create' and args.pd is not None:
            print(dao.create_physical_device(args.pd))
        elif args.cmd2 == 'up' and args.pd is not None:
            pdev = dao.get_physical_device(args.p_uid)
            if pdev is None:
                raise RuntimeError('Physical device not found.')

            pdev = pdev.dict()
            for k, v in args.pd.items():
                if pdev[k] != v:
                    pdev[k] = v

            pdev = PhysicalDevice.parse_obj(pdev)
            print(pretty_print_json(dao.update_physical_device(pdev)))
        elif args.cmd2 == 'rm':
            print(dao.delete_physical_device(args.p_uid))
    elif args.cmd1 == 'ld':
        if args.cmd2 == 'ls':
            devs = dao.get_logical_devices()
            tmp_list = list(map(lambda dev: dev.dict(exclude={'properties'}), devs))
            print(pretty_print_json(tmp_list))
        elif args.cmd2 == 'create' and args.ld is not None:
            print(dao.create_logical_device(args.ld))
        elif args.cmd2 == 'up' and args.ld is not None:
            ldev = dao.get_logical_device(args.l_uid)
            if ldev is None:
                raise RuntimeError('Logical device not found.')

            ldev = ldev.dict()
            for k, v in args.ld.items():
                if ldev[k] != v:
                    ldev[k] = v

            ldev = LogicalDevice.parse_obj(ldev)
            print(pretty_print_json(dao.update_logical_device(ldev)))
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
            dao.end_mapping(ld=args.l_uid)
        elif args.cmd2 == 'ls':
            if args.p_uid is not None:
                pretty_print_json(dao.get_current_device_mapping(pd=args.p_uid))
            elif args.l_uid is not None:
                map_list = dao.get_logical_device_mappings(args.l_uid)
                new_list = [m.dict() for m in map_list]
                print(pretty_print_json(new_list))

if __name__ == '__main__':
    main()
