import os, subprocess

from . import comment
from . import nodes
import sys, re
import glob
from cldoc.clang import cindex

from . import fs
from . import utf8

class DocumentMerger:
	reinclude = re.compile('#<cldoc:include[(]([^)]*)[)]>')
	reheading = re.compile('(.*)\\s*{#(?:([0-9]*):)?(.*)}')
	rename = re.compile('(?:.*)\\s*\\\\name\\s*([A-Za-z0-9_-]+)\\s*$')
	def merge(self, mfilter, files):
		newfiles=[]
		for filepath in files:
			gfiles=glob.glob(filepath)
			newfiles=newfiles+gfiles

		for f in newfiles:
			if os.path.basename(f).startswith('.'):
				continue
			if os.path.isdir(f):
				self.merge(mfilter, [os.path.join(f, x) for x in os.listdir(f)])
			elif f.endswith('.md'):
				self._merge_file(mfilter, f)

	def _split_categories(self, filename, contents):
		lines = contents.splitlines()

		ret = {}
		title={}
		category = None
		doc = []
		first = False
		ordered = []
		weight = {}
		this_weight=0
		this_title=''
		for line in lines:
			line = line.rstrip('\n')

			if first:
				first = False

				if line == '':
					continue
			heading=DocumentMerger.reheading.search(line)
			name=DocumentMerger.rename.search(line)
			if name:
				n1=name.group(0)
				n2=name.group(1)
			if name and name.group(1):
				category=name.group(1)
			elif heading:
				if heading.group(2):
					this_weight=int(heading.group(2))
				category=heading.group(3)
				this_title=heading.group(1).strip()
			else:
				doc.append(line)
		if not this_weight:
			this_weight=0
		if not category and len(doc) > 0:
			parts=filename.replace('\\','/').replace('.md','').split('/')
			category=parts[len(parts)-1]
			this_title=category

		if category:
			if not category in ret:
				ordered.append(category)
			title[category]=this_title
			ret[category] = "\n".join(doc)
			weight[category] = this_weight

		return [[c, ret[c],title[c],weight[c]] for c in ordered]

	def _normalized_qid(self, qid):
		#if qid == 'ref': #or qid == 'index':
			#return None

		if qid.startswith('::'):
			return qid[2:]

		return qid

	def _do_include(self, mfilter, filename, relpath):
		if not os.path.isabs(relpath):
			relpath = os.path.join(os.path.dirname(filename), relpath)

		return self._read_merge_file(mfilter, relpath)

	def _process_includes(self, mfilter, filename, contents):
		def repl(m):
			return self._do_include(mfilter, filename, m.group(1))

		return DocumentMerger.reinclude.sub(repl, contents)

	def _read_merge_file(self, mfilter, filename):
		if not mfilter is None:
			contents = utf8.utf8(subprocess.check_output([mfilter, filename]))
		else:
			contents = utf8.utf8(fs.fs.open(filename).read())

		return self._process_includes(mfilter, filename, contents)

	def _merge_file(self, mfilter, filename):
		contents = self._read_merge_file(mfilter, filename)
		categories = self._split_categories(filename, contents)

		for (category, docstr, cat_title, weight) in categories:
			# First, split off any order number from the front e.g. 3:name
			category=category.replace('::','_DOUBLECOLONSEPARATOR_')
			front_back= category.split(':')
			front=''
			if len(front_back)>1:
				category=front_back[1]
				front=front_back[0]
			else:
				category=front_back[0]
			category=category.replace('_DOUBLECOLONSEPARATOR_','::')
			parts = category.split('/')

			qid = self._normalized_qid(parts[0])

			# 'ref' means the root of the reference:  ##removing to allow for an index in the ref folder
			#if qid=='ref':
				#qid=None
			if not self.qid_to_node[qid]:
				self.add_categories([[qid,cat_title]])
				node = self.category_to_node[qid]
			else:
				node = self.qid_to_node[qid]
				if qid==None:
					node.set_title(cat_title)
			node.weight=weight
			node.merge_comment(comment.Comment(docstr,(filename,0,0,0), self.options), override=True)

	def add_categories(self, categories):
		root = None

		for category,title in categories:
			parts = category.split('::')

			root = self.root
			fullname = ''

			for i in range(len(parts)):
				part = parts[i]
				found = False

				if i != 0:
					fullname += '::'

				fullname += part

				for child in root.children:
					if isinstance(child, nodes.Category) and child.name == part:
						root = child
						found = True
						break

				if not found:
					s = nodes.Category(part,title)

					root.append(s)
					root = s

					self.category_to_node[fullname] = s
					self.qid_to_node[s.qid] = s
					self.all_nodes.append(s)

		return root

# vi:ts=4:et
