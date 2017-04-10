# (C) Datadog, Inc. 2013-2016
# (C) Brett Langdon <brett@blangdon.com> 2013
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)


# stdlib
from fnmatch import fnmatch
from os import stat
from os.path import abspath, basename, exists, join
import time
import re

# 3p
from scandir import walk

# project
from checks import AgentCheck
from config import _is_affirmative


class SubDirSizesCheck(AgentCheck):
    """This check is for monitoring and reporting metrics on the subdirectories for a provided directory

    WARNING: the user/group that dd-agent runs as must have access to stat the files in the desired directory

    Config options:
        "directory" - string, the directory to gather stats for. required
        "dirtagname" - string, the name of the tag used for the directory. defaults to "name"
        "subdirtagname" - string, the name of the tag used for the subdirectory. defaults to "subdir"
        "subdirtagname_regex" - string, pattern to use when parsing tags from a directory name. default None
        "subdirgauges" - boolean, when true a total stat will be emitted for each subdirectory. default False
        "rootdirtagname" - string, the name of the tag used for the root path. default "" (omitted from tags)
        "rootdirtagname_regex" - string, pattern to use when parsing tags from the root path. default ""
        "pattern" - string, the `fnmatch` pattern to use when reading the "directory"'s files. default "*"
        "recurse" - boolean, when true gather stats for the subdirectories recursively. default False
    """

    SOURCE_TYPE_NAME = 'system'

    def check(self, instance):
        if "directory" not in instance:
            raise Exception('DirectoryCheck: missing "directory" in config')

        directory = instance["directory"]
        abs_directory = abspath(directory)
        dirtagname = instance.get("dirtagname", "name")
        subdirtagname = instance.get("subdirtagname", "subdir")
        subdirtagname_regex = instance.get("subdirtagname_regex", "")
        rootdirtagname = instance.get("rootdirtagname", "")
        rootdirtagname_regex = instance.get("rootdirtagname_regex", "")
        pattern = instance.get("pattern", "*")
        recurse = instance.get("recurse", False)

        if not exists(abs_directory):
            raise Exception("DirectoryCheck: the directory (%s) does not exist" % abs_directory)

        self._get_stats(abs_directory, dirtagname, subdirtagname, subdirtagname_regex, rootdirtagname, rootdirtagname_regex, pattern, recurse)

    def _get_stats(self, directory, dirtagname, subdirtagname, subdirtagname_regex, rootdirtagname, rootdirtagname_regex, pattern, recurse):
        orig_dirtags = [dirtagname + ":%s" % directory]
        pat = re.compile(subdirtagname_regex)
        rootdirtagname_pat = re.compile(rootdirtagname_regex)

        # Initialize state for subdirectories
        subdirs = {}
        for root, dirs, files in walk(directory):
            if root == directory:
                for d in dirs:
                    subdir_path = join(root, d)
                    tags = []
                    if subdirtagname_regex:
                        m = pat.match(d)
                        if m:
                            # Subdir matches
                            tags += ["%s:%s" % (tagname, tagvalue) for tagname, tagvalue in m.groupdict().iteritems()]
                    else:
                        subdir_tag_value = d
                        tags += ["%s:%s" % (subdirtagname, subdir_tag_value)]

                    if rootdirtagname_regex:
                        m = rootdirtagname_pat.match(root)
                        if m:
                            tags += ["%s:%s" % (tagname, tagvalue) for tagname, tagvalue in m.groupdict().iteritems()]
                    elif rootdirtagname:
                        tags += ["%s:%s" % (rootdirtagname, root)]

                    subdirs[subdir_path] = {'name': d, 'files': 0, 'bytes': 0, 'tags': tags}
                # There should only be one case where root == directory, so safe to break
                break


        # Walk the entire directory and accumulate counts
        for root, dirs, files in walk(directory):
            directory_files = 0
            subdir_bytes = 0

            for filename in files:
                filename = join(root, filename)
                # check if it passes our filter
                if not fnmatch(filename, pattern):
                    continue

                directory_files += 1

                try:
                    file_stat = stat(filename)
                except OSError, ose:
                    self.warning("DirectoryCheck: could not stat file %s - %s" % (filename, ose))
                else:
                    subdir_bytes += file_stat.st_size

            for subdir in subdirs:
                # Append a trailing slash to prevent bad matches
                if root == subdir or (recurse and root.startswith("{0}/".format(subdir))):
                    subdirs[subdir]['files'] += directory_files
                    subdirs[subdir]['bytes'] += subdir_bytes


        # Iterate through subdirectory states and emit metrics
        for _, state in subdirs.iteritems():
            name = state['name']
            subdir_files = state['files']
            subdir_bytes = state['bytes']
            tags = state['tags']

            tags = list(orig_dirtags) + tags


            self.gauge("system.sub_dir.bytes", subdir_bytes, tags=tags)
            self.gauge("system.sub_dir.files", subdir_files, tags=tags)

