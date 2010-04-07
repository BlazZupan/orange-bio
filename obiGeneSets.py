"""
Getting genesets from KEGG and GO.

Maintainer: Marko Toplak
"""
from __future__ import with_statement

import obiKEGG, orange
import os
import obiGO
import cPickle as pickle
#import pickle
import orngServerFiles
import obiTaxonomy
import tempfile
import obiGeneSets
import sys
from collections import defaultdict

sfdomain = "gene_sets"

def nth(l,n):
    return [ a[n] for a in l]

class GeneSet(object):

    def __init__(self, genes=None, name=None, id=None, \
        description=None, link=None, organism=None, hierarchy=None, pair=None):
        """
        pair can be (id, listofgenes) - it is used before anything else.
        """
        if genes == None:
            genes = []

        self.hierarchy = hierarchy
        self.genes = set(genes)
        self.name = name
        self.id = id
        self.description = description
        self.link = link
        self.organism = organism

        if pair:
            self.id, self.genes = pair[0], set(pair[1])

    """
    the following functions are needed for sets of gene sets to be able
    to assess equality
    """

    def __hash__(self):
        return self.id.__hash__() + self.name.__hash__()

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def size(self):
        return len(self.genes)

    def cname(self, source=True, name=True):
        """ Constructs a gene set name with the hierarchy. """
        oname = self.id
        if source and self.hierarchy:
            oname = "[ " + ", ".join(self.hierarchy) + " ] " + oname
        if name and self.name:
            oname = oname + " " + self.name
        return oname

    def to_odict(self, source=True, name=True):
        """
        Returns a pair (id, listofgenes), like in old format.
        """
        return self.cname(source=source, name=name), self.genes

    def __repr__(self):
        return "GeneSet(" + ", ".join( [ 
            "id=" + str(self.id),
            "genes=" + str(self.genes),
            "name=" + str(self.name),
            "link=" + str(self.link),
            "hierarchy=" + str(self.hierarchy)
        ]) + ")"

class GeneSetIDException(Exception):
    pass

class GeneSets(set):
    
    def __init__(self, input=None):
        """
        odict are genesets in old dict format.
        gs are genesets in new format
        """
        if input != None and len(input) > 0:
            if hasattr(input, "items"):
                for i,g in input.items():
                    self.add(obiGeneSets.GeneSet(pair=(i,g)))
            else:
                self.update(input)

    def to_odict(self):
        """ Return gene sets in old dictionary format. """
        return dict(gs.to_odict() for gs in self)

    def set_hierarchy(self, hierarchy):
        """ Sets hierarchy for all gene sets """
        for gs in self:
            gs.hierarchy = hierarchy

    def __repr__(self):
        return "GeneSets(" + set.__repr__(self) + ")"

    def common_org(self):
        """ Returns the common organism. """
        if len(self) == 0:
            raise GenesetRegException("Empty gene sets.")

        organisms = set(a.organism for a in self)

        try:
            return only_option(organisms)
        except:
            raise GenesetRegException("multiple organisms: " + str(organisms))

    def hierarchies(self):
        """ Returns all hierachies """
        if len(self) == 0:
            raise GenesetRegException("Empty gene sets.")
        return set(a.hierarchy for a in self)

    def common_hierarchy(self):
        hierarchies = self.hierarchies()

        def common_hierarchy1(hierarchies):
            def hier(l): return set(map(lambda x: x[:currentl], hierarchies))
            currentl = max(map(len, hierarchies))
            while len(hier(currentl)) > 1:
                currentl -= 1
            return only_option(hier(currentl))

        return common_hierarchy1(hierarchies)

    def split_by_hierarchy(self):
        """ Splits gene sets by hierarchies. """
        hd = dict((h,obiGeneSets.GeneSets()) for h in  self.hierarchies())
        for gs in self:
            hd[gs.hierarchy].add(gs)
        return hd.values()

def goGeneSets(org):
    """Returns gene sets from GO."""

    ontology = obiGO.Ontology()
    annotations = obiGO.Annotations(org, ontology=ontology)

    genesets = []
    link_fmt = "http://amigo.geneontology.org/cgi-bin/amigo/term-details.cgi?term=%s"
    for termn, term in ontology.terms.items():
        genes = annotations.GetAllGenes(termn)
        hier = ("GO", term.namespace)
        if len(genes) > 0:
            gs = obiGeneSets.GeneSet(id=termn, name=term.name, genes=genes, hierarchy=hier, organism=org, link=link_fmt % termn) 
            genesets.append(gs)

    return obiGeneSets.GeneSets(genesets)

def keggGeneSets(org):
    """
    Returns gene sets from KEGG pathways.
    """
    kegg = obiKEGG.KEGGOrganism(org)

    genesets = []
    for id in kegg.pathways():
        pway = obiKEGG.KEGGPathway(id)
        hier = ("KEGG",)
        gs = obiGeneSets.GeneSet(id=id, name=pway.title, genes=kegg.get_genes_by_pathway(id), hierarchy=hier, organism=org, link=pway.link)
        genesets.append(gs)

    return obiGeneSets.GeneSets(genesets)

def omimGeneSets():
    """
    Return gene sets from OMIM (Online Mendelian Inheritance in Man) diseses
    """
    import obiOMIM
    genesets = [GeneSet(id=disease.id, name=disease.name, genes=obiOMIM.disease_genes(disease), hierarchy=("OMIM",), organism="9606",
                    link=("http://www.ncbi.nlm.nih.gov/entrez/dispomim.cgi?id=" % disease.id if disease.id else None)) \
                    for disease in obiOMIM.diseases()]
    return GeneSets(genesets)

def loadGMT(contents, name):
    """
    Eech line consists of tab separated elements. First is
    the geneset name, next is it's description. 
    
    For now the description is skipped.
    """
    def hline(s):
        tabs = [ tab.strip() for tab in s.split("\t") ]
        return  obiGeneSets.GeneSet(id=tabs[0], description=tabs[1], hierarchy=(name,), genes=tabs[2:])

    def handleNELines(s, fn):
        """
        Run function on nonempty lines of a string.
        Return a list of results for each line.
        """
        lines = s.split("\n")
        lines = [ l.strip() for l in lines ]
        lines = filter(lambda x: x != "", lines)
        return [ fn(l) for l in lines ]

    return obiGeneSets.GeneSets(handleNELines(contents, hline))

"""
We have multiple paths for gene set data:
buffer/bigfiles/gene_sets
and
buffer/gene_sets_local
both have available.txt
"""

def omakedirs(dir):
    try:
        os.makedirs(dir)
    except OSError:
        pass

def local_path():
    """ Returns local path for gene sets. Creates it if it does not exists
    yet. """
    import orngEnviron
    pth = os.path.join(orngEnviron.directoryNames["bufferDir"], "gene_sets_local")
    omakedirs(pth)
    return pth

def build_index(dir):
    """ Returns gene set availability index for some folder. """
    pass

class GenesetRegException(Exception): pass

def only_option(a):
    if len(a) == 1:
        return list(a)[0]
    else:
        raise Exception()

def filename(hierarchy, organism):
    """ Obtain a filename for given hierarchy and organism. """
    return "gs_" + "_._".join(hierarchy + \
        (organism if organism != None else "",)) + ".pck"

def filename_parse(fn):
    """ Returns a hierarchy and the organism from the filename."""
    fn = fn[3:-4]
    parts = fn.split("_._")
    hierarchy = tuple(parts[:-1])
    org = parts[-1] if parts[-1] != "" else None
    return hierarchy, org

def is_genesets_file(fn):
    return fn.startswith("gs_") and fn.endswith(".pck")

def list_local():
    """ Returns available gene sets from the local repository:
    a list of (hierarchy, organism, on_local) """
    pth = local_path()
    gs_files = filter(is_genesets_file, os.listdir(pth))
    return [ filename_parse(fn) + (True,) for fn in gs_files ]
    
def list_serverfiles_from_flist(flist):
    gs_files = filter(is_genesets_file, flist)
    localfiles = set(orngServerFiles.listfiles(sfdomain))
    return [ filename_parse(fn) + \
        ((True,) if fn in localfiles else (False,)) for fn in gs_files ]

def list_serverfiles_conn(serverfiles=None):
    """ Returns available gene sets from the server files
    repository: a list of (hierarchy, organism, on_local) """
    if serverfiles == None:
        serverfiles = orngServerFiles.ServerFiles()
    flist = serverfiles.listfiles(sfdomain)
    return list_serverfiles_from_flist(flist)

def list_serverfiles():
    fname = orngServerFiles.localpath_download(sfdomain, "index.pck")
    flist = pickle.load(open(fname, 'r'))
    return list_serverfiles_from_flist(flist)

def list_all():
    """
    return a list of (hier, org, avalable_locally)
    If something for a specific (hier, org) is not downloaded
    yet, show it as not-local. """
    flist = list_local() + list_serverfiles()
    d = {}
    for h,o,local in flist:
        d[h,o] = min(local, d.get((h,o),True))
    return [ (h,o,local) for (h,o),local in d.items() ]

def update_server_list(serverfiles_upload, serverfiles_list=None):
    if serverfiles_list == None:
        serverfiles_list = orngServerFiles.ServerFiles()

    flist = map(lambda x: filename(*x[:2]), list_serverfiles_conn(serverfiles_list))

    tfname = pickle_temp(flist)
    
    try:
        fn = "index.pck"
        title = "Gene sets: index"
        tags = [ "gene sets", "index", "essential" ]
        serverfiles_upload.upload(sfdomain, fn, tfname, title, tags)
        serverfiles_upload.unprotect(sfdomain, fn)
    except Exception,e:
        raise e
    finally:
        os.remove(tfname)

def register_local(genesets):
    """ Registers using the common hierarchy and organism. """
    pth = local_path()

    org = genesets.common_org()
    hierarchy = genesets.common_hierarchy()
    fn = filename(hierarchy, org)

    with open(os.path.join(pth, fn), "w") as f:
        pickle.dump(genesets, f)

    return fn

def pickle_temp(obj):
    """ Pickle a file to a temporary file returns its name """
    fd,tfname = tempfile.mkstemp()
    os.close(fd)
    f = open(tfname, 'wb')
    pickle.dump(obj, f)
    f.close()
    return tfname

def register_serverfiles(genesets, serverFiles):
    """ Registers using the common hierarchy and organism. """
    org = genesets.common_org()
    hierarchy = genesets.common_hierarchy()
    fn = filename(hierarchy, org)

    #save to temporary file
    tfname = pickle_temp(genesets)
    
    try:
        taxname = obiTaxonomy.name(org)
        title = "Gene sets: " + ", ".join(hierarchy) + \
            ((" (" + taxname + ")") if org != None else "")
        tags = list(hierarchy) + [ "gene sets", taxname ] + \
            ([ "essential" ] if org in obiTaxonomy.essential_taxids() else [] )
        serverFiles.upload(sfdomain, fn, tfname, title, tags)
        serverFiles.unprotect(sfdomain, fn)
    except Exception, e:
        raise e
    finally:
        os.remove(tfname)

    update_server_list(serverFiles)

def register(genesets, serverFiles=None):
    """
    Hierarchy is induced from the gene set names.
    """
    if serverFiles == None:
        register_local(genesets)
    else:
        register_serverfiles(genesets, serverFiles)

def build_hierarchy_dict(files):
    hierd = defaultdict(list)
    for ind,f in enumerate(files):
        hier, org = f
        for i in range(len(hier)+1):
            hierd[(hier[:i], org)].append(ind)
    return hierd

def load_local(hierarchy, organism):
    files = map(lambda x: x[:2], list_local())

    hierd = build_hierarchy_dict(files)

    out = GeneSets()
    for (h, o) in [ files[i] for i in hierd[(hierarchy, organism)]]:
        fname = os.path.join(local_path(), filename(h, o))
        out.update(pickle.load(open(fname, 'r')))
    return out

def load_serverfiles(hierarchy, organism):
    files = map(lambda x: x[:2], list_serverfiles())

    hierd = build_hierarchy_dict(files)

    out = GeneSets()
    for (h, o) in [ files[i] for i in hierd[(hierarchy, organism)]]:
        fname = orngServerFiles.localpath_download(sfdomain, 
            filename(h, o))
        out.update(pickle.load(open(fname, 'r')))
    return out

def load(hierarchy, organism):
    """ First try to load from the local registred folder, then
    from the server files. """
    ret = load_local(hierarchy, organism)
    ret.update(load_serverfiles(hierarchy, organism))
    return ret

def collections(*args):
    """
    Input is a list of collections.
    Collection can either be a tuple (hierarchy, orgranism), where
    hierarchy is a tuple also.
    """
    result = obiGeneSets.GeneSets()

    for collection in args:
        if isinstance(collection, obiGeneSets.GeneSets):
            result.update(collection)
        elif issequencens(collection): #have a hierarchy, organism specification
            new = load(*collection)
            result.update(new)
        else:
            if collection.lower()[-4:] == ".gmt": #format from webpage
                result.update(loadGMT(open(collection,"rt").read(), collection))
            else:
                raise Exception("collection() accepts files in .gmt format only.")
 
    return result

def issequencens(x):
    "Is x a sequence and not string ? We say it is if it has a __getitem__ method and it is not an instance of basestring."
    return hasattr(x, '__getitem__') and not isinstance(x, basestring)

def upload_genesets(rsf):
    """
    Builds the default gene sets and 
    """
    orngServerFiles.update_local_files()

    genesetsfn = [ keggGeneSets, goGeneSets ]
    organisms = obiTaxonomy.common_taxids()
    for fn in genesetsfn:
        for org in organisms:
            print "Uploading ORG", org, fn
            try:
                genesets = fn(org).split_by_hierarchy()
                for gs in genesets:
                    print "registering", gs.common_hierarchy()
                    register_serverfiles(gs, rsf)
                    print "successfull", gs.common_hierarchy()
            except Exception:
                print "Not successfull"

if __name__ == "__main__":
    gs = keggGeneSets("9606")
    #print len(collections(keggGeneSets("9606"),(("KEGG",),"9606"), "C5.BP.gmt"))
    #print len(collections((("KEGG",),"9606"), "C5.BP.gmt"))
    print sorted(list_all())
    print len(collections((("KEGG",),"9606"), (("GO",), "9606"), "C5.BP.gmt"))
    #register_local(keggGeneSets("9606"))
    #register_local(goGeneSets("9606"))
    #register_serverfiles(gs, rsf)
    #print list_serverfiles_conn()
    #print "Server list from index", list_serverfiles()
    #rsf = orngServerFiles.ServerFiles(username=sys.argv[1], password=sys.argv[2])
    #upload_genesets(rsf)
