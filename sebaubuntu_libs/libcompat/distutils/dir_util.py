#
# Copyright (C) 2023 Python Packaging Authority
# Copyright (C) 2024 Sebastiano Barezzi
#
# SPDX-License-Identifier: MIT
#

import errno
import os

from sebaubuntu_libs.liblogging import LOGI

from .errors import DistutilsFileError, DistutilsInternalError

# cache for by mkpath() -- in addition to cheapening redundant calls,
# eliminates redundant "creating /foo/bar/baz" messages in dry-run mode
_path_created = {}


def mkpath(name, mode=0o777, verbose=1, dry_run=0):  # noqa: C901
	"""Create a directory and any missing ancestor directories.

	If the directory already exists (or if 'name' is the empty string, which
	means the current directory, which of course exists), then do nothing.
	Raise DistutilsFileError if unable to create some directory along the way
	(eg. some sub-path exists, but is a file rather than a directory).
	If 'verbose' is true, print a one-line summary of each mkdir to stdout.
	Return the list of directories actually created.

	os.makedirs is not used because:

	a) It's new to Python 1.5.2, and
	b) it blows up if the directory already exists (in which case it should
	   silently succeed).
	"""

	global _path_created

	# Detect a common bug -- name is None
	if not isinstance(name, str):
		raise DistutilsInternalError(f"mkpath: 'name' must be a string (got {name!r})")

	# XXX what's the better way to handle verbosity? print as we create
	# each directory in the path (the current behaviour), or only announce
	# the creation of the whole path? (quite easy to do the latter since
	# we're not using a recursive algorithm)

	name = os.path.normpath(name)
	created_dirs = []
	if os.path.isdir(name) or name == '':
		return created_dirs
	if _path_created.get(os.path.abspath(name)):
		return created_dirs

	(head, tail) = os.path.split(name)
	tails = [tail]  # stack of lone dirs to create

	while head and tail and not os.path.isdir(head):
		(head, tail) = os.path.split(head)
		tails.insert(0, tail)  # push next higher dir onto stack

	# now 'head' contains the deepest directory that already exists
	# (that is, the child of 'head' in 'name' is the highest directory
	# that does *not* exist)
	for d in tails:
		# print "head = %s, d = %s: " % (head, d),
		head = os.path.join(head, d)
		abs_head = os.path.abspath(head)

		if _path_created.get(abs_head):
			continue

		if verbose >= 1:
			LOGI("creating %s", head)

		if not dry_run:
			try:
				os.mkdir(head, mode)
			except OSError as exc:
				if not (exc.errno == errno.EEXIST and os.path.isdir(head)):
					raise DistutilsFileError(
						f"could not create '{head}': {exc.args[-1]}"
					)
			created_dirs.append(head)

		_path_created[abs_head] = 1
	return created_dirs

def copy_tree(  # noqa: C901
	src,
	dst,
	preserve_mode=1,
	preserve_times=1,
	preserve_symlinks=0,
	update=0,
	verbose=1,
	dry_run=0,
):
	"""Copy an entire directory tree 'src' to a new location 'dst'.

	Both 'src' and 'dst' must be directory names.  If 'src' is not a
	directory, raise DistutilsFileError.  If 'dst' does not exist, it is
	created with 'mkpath()'.  The end result of the copy is that every
	file in 'src' is copied to 'dst', and directories under 'src' are
	recursively copied to 'dst'.  Return the list of files that were
	copied or might have been copied, using their output name.  The
	return value is unaffected by 'update' or 'dry_run': it is simply
	the list of all files under 'src', with the names changed to be
	under 'dst'.

	'preserve_mode' and 'preserve_times' are the same as for
	'copy_file'; note that they only apply to regular files, not to
	directories.  If 'preserve_symlinks' is true, symlinks will be
	copied as symlinks (on platforms that support them!); otherwise
	(the default), the destination of the symlink will be copied.
	'update' and 'verbose' are the same as for 'copy_file'.
	"""
	from .file_util import copy_file

	if not dry_run and not os.path.isdir(src):
		raise DistutilsFileError("cannot copy tree '%s': not a directory" % src)
	try:
		names = os.listdir(src)
	except OSError as e:
		if dry_run:
			names = []
		else:
			raise DistutilsFileError(f"error listing files in '{src}': {e.strerror}")

	if not dry_run:
		mkpath(dst, verbose=verbose)

	outputs = []

	for n in names:
		src_name = os.path.join(src, n)
		dst_name = os.path.join(dst, n)

		if n.startswith('.nfs'):
			# skip NFS rename files
			continue

		if preserve_symlinks and os.path.islink(src_name):
			link_dest = os.readlink(src_name)
			if verbose >= 1:
				LOGI("linking %s -> %s", dst_name, link_dest)
			if not dry_run:
				os.symlink(link_dest, dst_name)
			outputs.append(dst_name)

		elif os.path.isdir(src_name):
			outputs.extend(
				copy_tree(
					src_name,
					dst_name,
					preserve_mode,
					preserve_times,
					preserve_symlinks,
					update,
					verbose=verbose,
					dry_run=dry_run,
				)
			)
		else:
			copy_file(
				src_name,
				dst_name,
				preserve_mode,
				preserve_times,
				update,
				verbose=verbose,
				dry_run=dry_run,
			)
			outputs.append(dst_name)

	return outputs
