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
        "subdirgauges" - boolean, when true a total stat will be emitted for each subdirectory. default False
        "pattern" - string, the `fnmatch` pattern to use when reading the "directory"'s files. default "*"
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
        pattern = instance.get("pattern", "*")

        if not exists(abs_directory):
            raise Exception("DirectoryCheck: the directory (%s) does not exist" % abs_directory)

        self._get_stats(abs_directory, dirtagname, subdirtagname, subdirtagname_regex, pattern)

    def _get_stats(self, directory, dirtagname, subdirtagname, subdirtagname_regex, pattern):
        orig_dirtags = [dirtagname + ":%s" % directory]
        directory_bytes = 0
        directory_files = 0
        recurse_count = 0
        for root, dirs, files in walk(directory):
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

            subdir_tag_value = basename(root)
            if recurse_count > 0:
                dirtags = list(orig_dirtags)
                if subdirtagname_regex:
                    pat = re.compile(subdirtagname_regex)
                    m = pat.match(subdir_tag_value)
                    if m:
                        # We got a match, use the groupdict to tagify the keys
                        for tagname, tagvalue in m.groupdict().iteritems():
                            dirtags = ["%s:%s" % (tagname, tagvalue)] + dirtags
                else:
                    dirtags = [subdirtagname + ":%s" % subdir_tag_value] + dirtags

                # If we've descended in to a subdir then let's emit total for the subdir

                self.gauge("system.sub_dir.bytes", subdir_bytes, tags=dirtags)
                self.gauge("system.sub_dir.files", directory_files, tags=orig_dirtags)

            # os.walk gives us all sub-directories and their files
            # if we do not want to do this recursively and just want
            # the top level directory we gave it, then break
            recurse_count += 1
