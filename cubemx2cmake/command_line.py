""" This is the implementation of stm32_c2c command """



import shutil
import os.path
import string
import sys
import os
import re
from argparse import ArgumentParser
from configparser import ConfigParser
from string import Template
from pkg_resources import resource_filename
from xml.etree import ElementTree

with open('.cproject', 'rt') as f:
    tree = ElementTree.parse(f)


def getDef():
    definition = ""
    for node in tree.iter('cconfiguration'):
        for opt in node.iter('option'):
            if(opt.attrib.get('superClass') == 'gnu.c.compiler.option.preprocessor.def.symbols'):
                for listOpt in opt.iter('listOptionValue'):
                            value = ""
                            if listOpt.attrib.get('value').find('weak') != -1:
                                value = '\'-D' + listOpt.attrib.get('value') + '\''
                            elif listOpt.attrib.get('value').find('packed') != -1:
                                value = '\'-D' + listOpt.attrib.get('value') + '\''
                            else:
                                value = '-D' + listOpt.attrib.get('value')
                            definition += 'add_definitions('+ value +')\n'
        break
    return definition

# Return codes
C2M_ERR_SUCCESS             =  0
C2M_ERR_INVALID_COMMANDLINE = -1
C2M_ERR_LOAD_TEMPLATE       = -2
C2M_ERR_NO_PROJECT          = -3
C2M_ERR_PROJECT_FILE        = -4
C2M_ERR_IO                  = -5
C2M_ERR_NEED_UPDATE         = -6

# Configuration

# STM32 MCU to compiler flags.
mcu_regex_to_cflags_dict = {
    'STM32(F|L)0': '-mcpu=cortex-m0',
    'STM32(F|L)1': '-mcpu=cortex-m3',
    'STM32(F|L)2': '-mcpu=cortex-m3',
    'STM32(F|L)3': '-mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mfloat-abi=hard',
    'STM32(F|L)4': '-mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mfloat-abi=hard',
    'STM32(F|L)7': '-mcpu=cortex-m7 -mfpu=fpv4-sp-d16 -mfloat-abi=hard',
}

def main():
    """ Function entry point for running script from command line """
    _main(sys.argv[1:])


def _main(args):
    """ Runnable code with CLI args for testing convenience"""
    proj_folder_path = os.path.abspath('.')
    if not os.path.isdir(proj_folder_path):
        sys.stderr.write("STM32CubeMX \"Toolchain Folder Location\" not found: {}\n".format(proj_folder_path))
        sys.exit(C2M_ERR_INVALID_COMMANDLINE)

    proj_name = os.path.splitext(os.path.basename(proj_folder_path))[0]
    ac6_project_path = os.path.join(proj_folder_path,'.project')
    ac6_cproject_path = os.path.join(proj_folder_path,'.cproject')
    if not (os.path.isfile(ac6_project_path) and os.path.isfile(ac6_cproject_path)):
        sys.stderr.write("SW4STM32 project not found, use STM32CubeMX to generate a SW4STM32 project first\n")
        sys.exit(C2M_ERR_NO_PROJECT)


    ctx = []

    c_set = {}
    c_set['source_endswith'] = '.c'
    c_set['source_subst'] = ''
    c_set['inc_endswith'] = '.h'
    c_set['inc_subst'] = ''
    c_set['first'] = True
    c_set['relpath_stored'] = ''
    ctx.append(c_set)

    asm_set = {}
    asm_set['source_endswith'] = '.s'
    asm_set['source_subst'] = ''
    asm_set['inc_endswith'] = '.inc'
    asm_set['inc_subst'] = 'AS_INCLUDES='
    asm_set['first'] = True
    asm_set['relpath_stored'] = ''
    ctx.append(asm_set)

    for path, dirs, files in os.walk(proj_folder_path):
        for file in files:
            for s in ctx:

                if file.endswith(s['source_endswith']):
                    s['source_subst'] += ' '
                    relpath = os.path.relpath(path,proj_folder_path)

                    #Split Windows style paths into tokens
                    #Unix style path emit a single token
                    relpath_split = relpath.split('\\')
                    for path_tok in relpath_split:
                        #Last token does not have a trailing slash
                        if path_tok == relpath_split[0]:
                            s['source_subst'] += path_tok
                        else:
                            s['source_subst'] += '/' + path_tok
                    s['source_subst'] += '/' + file

                if file.endswith(s['inc_endswith']):
                    relpath = os.path.relpath(path,proj_folder_path)

                    #only include a path once
                    if relpath != s['relpath_stored']:
                        s['relpath_stored'] = relpath

                        #If this is the first include, we already have the 'C_INCLUDES ='
                        if s['first']:
                            s['first'] = False
                            s['inc_subst'] += ''
                        else:
                            s['inc_subst'] += ' '


                        #Split Windows style paths into tokens
                        #Unix style path emit a single token
                        relpath_split = relpath.split('\\')
                        for path_tok in relpath_split:
                            #Last token does not have a trailing slash
                            if path_tok == relpath_split[0]:
                                s['inc_subst'] += path_tok
                            else:
                                s['inc_subst'] += '/' + path_tok         
                    
    # .cproject file
    root = tree.getroot()

    # MCU
    mcu_node = root.find('.//toolChain/option[@superClass="fr.ac6.managedbuild.option.gnu.cross.mcu"][@name="Mcu"]')
    try:
        mcu_str = mcu_node.attrib.get('value')
    except Exception as e:
        sys.stderr.write("Unable to find target MCU node. Error: {}\n".format(str(e)))
        sys.exit(C2M_ERR_PROJECT_FILE)
    for mcu_regex_pattern, cflags in mcu_regex_to_cflags_dict.items():
        if re.match(mcu_regex_pattern, mcu_str):
            cflags_subst = cflags
            ld_subst = cflags
            break
    else:
        sys.stderr.write("Unknown MCU: {}\n".format(mcu_str))
        sys.stderr.write("Please contact author for an update of this utility.\n")
        sys.stderr.exit(C2M_ERR_NEED_UPDATE)

    # AS symbols
    as_defs_subst = 'AS_DEFS ='

    # C symbols
    c_defs_subst = 'C_DEFS ='
    c_def_node_list = root.findall('.//tool/option[@valueType="definedSymbols"]/listOptionValue')
    for c_def_node in c_def_node_list:
        c_def_str = c_def_node.attrib.get('value')
        if c_def_str:
            c_defs_subst += ' -D{}'.format(c_def_str)

    # Link script
    ld_script_node_list = root.find('.//tool/option[@superClass="fr.ac6.managedbuild.tool.gnu.cross.c.linker.script"]')
    try:
        ld_script_path = ld_script_node_list.attrib.get('value')
    except Exception as e:
        sys.stderr.write("Unable to find link script. Error: {}\n".format(str(e)))
        sys.exit(C2M_ERR_PROJECT_FILE)
    ld_script_name = os.path.basename(ld_script_path)
    ld_script_subst = ld_script_name


    arg_parser = ArgumentParser()
    arg_parser.add_argument("cube_file", default="", nargs='?',
        help="CubeMX project file (if not specified, the one contained in current directory is used)")
    arg_parser.add_argument("-i", "--interface", default="stlink-v2",
        help="OpenOCD debug interface name (stlink-v2 is used by default)")
    arg_parser.add_argument("-m", "--memory-start", default="0x08000000",
        help="Flash memory start address (0x08000000 by default)")
    arg_parser.add_argument("-g", "--gdb-port", default="3333",
        help="The port for connecting with GDB")
    arg_parser.add_argument("-t", "--telnet-port", default="4444",
        help="The port for connecting via telnet")
    args = arg_parser.parse_args(args)

    if args.cube_file != "":
        cube_file = args.cube_file
    else:
        ioc_files = []
        # Check if there is a single *.ioc file
        for file in os.listdir("."):
            if file.endswith(".ioc"):
                ioc_files.append(file)
        if len(ioc_files) == 1:
            print(ioc_files[0]+" was found!")
            cube_file = ioc_files[0]
        else:
            print("No input file was specified!")
            exit(0)

    cube_config_parser = ConfigParser()
    try:
        # *.ioc files have a INI-like format, but without section, so we need to create one
        cube_config_parser.read_string(u"[section]\n"+open(cube_file).read())
    except FileNotFoundError:
        print("Input file doesn't exist!")
        exit(0)
    except IOError:
        print("Input file doesn't exist, is broken or access denied.")
        exit(0)

    # Get the data from the fake section we created earlier
    cube_config = dict(cube_config_parser["section"])

    try:
        mcu_family = cube_config["mcu.family"]
        mcu_username = cube_config["mcu.username"]
        prj_name = cube_config["projectmanager.projectname"]
        make_defination = getDef()
    except KeyError:
        print("Input file is broken!")
        exit(0)

    params = {
        "PRJ_NAME": prj_name,
        "MCU_FAMILY": mcu_family+"xx",
        "MCU_LINE": mcu_username[:9]+"x"+cube_config["mcu.name"][13],
        "MCU_LINKER_SCRIPT": ld_script_subst,
        "MCU_ARCH": cflags_subst,
        "TARGET": mcu_family+"x",
        "INTERFACE_NAME": args.interface,
        "GDB_PORT": args.gdb_port,
        "TELNET_PORT": args.telnet_port,
        "MAKE_DEFINATION": make_defination,
        "MCU_SOURCE": c_set['source_subst'] + ' ' + asm_set['source_subst'],
    	"MCU_INCLUDE_FOLDER": c_set['inc_subst'],
        "MCU_INCLUDE_H": c_set['inc_subst'].replace(' ' , '/*.h ')
    }

    templates = os.listdir(resource_filename(__name__, "templates"))

    for template_name in templates:
        template_fn = resource_filename(__name__, "templates/%s" % (template_name))
        with open(template_fn, "r") as template_file:
            template = Template(template_file.read())
        try:
            with open(template_name.replace(".template",""), "w") as target_file:
                target_file.write(template.safe_substitute(params))
        except IOError:
            print("Cannot write output files! Maybe write access to the current directory is denied.")
            exit(0)

    print("All files were successfully generated!")

    return params

