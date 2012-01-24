""" Interface to retrieve gene networks from GeneMANIA server

Example::
    
    >>> conn = Connection("http://localhost:8080/genemania")
    >>> net = conn.retrieve(org="3702", ["PHYB", "ELF3", 'COP1", "SPA1", "FUS9"])
    >>> net.save("graph.net")
    >>> net.retrieve(org="3702", genes=["CIP1"], m="bp", r=100).save("CIP1.net")

    

"""

import urllib2
import urllib
import re
import posixpath
from xml.dom import minidom

import orange
import orngNetwork

DEFAULT_SERVER = "http://193.2.72.57:8080/genemania"

_TAX_ID_2_INDEX = {"3702": 1,
                   "6239": 2,
                   "7227": 3,
                   "9606": 4,
                   "10090": 5,
                   "4932": 6
                   }
class Connection(object):
    _RE_TOKEN = re.compile(r'<li\s+id\s*=\s*"menu_save"\s*token\s*=\s*"([0-9]+)"><label>Save</label>')
    _RE_NETWORK_TAB = re.compile(r'^<div\s*id\s*=\s*"networks_tab"\s*class\s*=\s*"tab">*?^</div>', re.MULTILINE)
    _RE_NETWORK_GROUP_NAMES = re.compile(r'<div\s*class\s*=\s*"network_name"\s*id\s*=\s*"networkGroupName([0-9]+)"\s*>\s*([a-zA-Z0-9_\- ]+)\s*</div>')
    _RE_NETWORK_NAMES = re.compile(r'<div\s*class\s*=\s*"network_name"\s*id\s*=\s*"networkName([0-9]+)"\s*>\s*([a-zA-Z0-9_\- ]+)\s*</div>')

    def __init__(self, address=DEFAULT_SERVER):
        """ Construct a Connection instance for GeneMANIA server at `address`
        
        :param address: URL address of GeneMANIA server
        :type address: str
        """
        self.address = address
                  
        
    def retrieveXML(self, org="9606", genes=[], m="automatic", r=10, token=None):
        """ Same as `retrieve` but return the network as an xml string
        """
        if token is None:
            page = self.retrieveHtmlPage(org, genes, m, r)
#            query = self._queryPage(org, genes, m, r)
#            stream = urllib2.urlopen(query)
#            page = stream.read()
            match = self._RE_TOKEN.findall(page)
        
            if match:
                token = match[0]
            else:
                raise ValueError("Invalid query. %s" % self._queryPage(org, genes, m, r))
        
        query = self._queryGraph(token)
        stream = urllib2.urlopen(query)
        graph = stream.read()
        self._graph = graph
        return graph
    
    def retrieveHtmlPage(self, org="9606", genes=[], m="automatic", r=10):
        """ Retrieve the HTML page (contains token to retrieve the graph, network descriptions ...)"
        """
        query = self._queryPage(org, genes, m, r)
        stream = urllib2.urlopen(query)
        page = stream.read()
        self._page = page
        return page
    
    def validate(self, org, genes):
        """ Validate gene names for organism. Return a two 
        tuple, one with known and one with unknown genes
        """
        
        organism = _TAX_ID_2_INDEX.get(org, 1)
        genes = "; ".join(genes)
        data = urllib.urlencode([("organism", str(organism)), ("genes", genes)])
        validatorUrl = posixpath.join(self.address, "validator")
        stream = urllib2.urlopen(validatorUrl, data)
        response = stream.read()
        dom = minidom.parseString(response)
        return parseValidationResponse(dom)
        
        
        
    def _queryPage(self, org, genes, m, r):
        return posixpath.join(self.address, "link?o=%s&g=%s&m=%s&r=%i" % (org, "|".join(genes), m, r)) 
    
    
    def _queryGraph(self, token):
        return posixpath.join(self.address, "pages/graph.xhtml?token=%s" % token)
    
    
    def retrieve(self, org, genes, m="automatic", r=10):
        """ Retrieve orngNetwork.Network instance representing the network for
        the query, (See 
        `http://193.2.72.57:8080/genemania/pages/help.jsf#section/link`_ for
        more details) 
        
        :param org: NCBI taxonomy identifier (A. thaliana=3702, C. elegans=6239,
                    D. melanogaster=7227, H. sapiens=9606, M. musculus=10090
                    S. cerevisiae=4932)
        :type org: str
        
        :param genes: query genes
        :type genes: list
        
        :param m: network combining method; must be one of the following:
                    * "automatic_relevance": Assigned based on query genes
                    * "automatic": Automatically selected weighting method
                       (Default)
                    * "bp": biological process based
                    * "mf": molecular function based
                    * "cc": cellular component based
                    * "average": equal by data type
                    * "average_category: equal by network
        :type m: str
        
        :param r: the number of results generated by GeneMANIA (must be in 
                  range 1..100
        :type r: int
        """
        xml = self.retrieveXML(org, genes, m, r)
        dom = minidom.parseString(xml)
        graph = parse(dom)
        return graph
    
        
    
def parse(DOM):
    """ Parse the graph DOM as returned from geneMANIA server and return
    an orngNetwork.Network instance
    """
    nodes = DOM.getElementsByTagName("node")
    edges = DOM.getElementsByTagName("edge")
    from collections import defaultdict
    graphNodes = {}
    graphEdges = defaultdict(list)
    
    def parseAttributes(element):
        return dict([(key, value) for key, value in element.attributes.items()])
    
    def parseText(element):
        text = u""
        for el in element.childNodes:
            if isinstance(el, minidom.Text):
                text += el.wholeText
        return text
                
    def parseData(node):
        data = node.getElementsByTagName("data")
        parsed = {}
        for el in data:
            attrs = parseAttributes(el)
            key = attrs["key"]
            parsed[key] = parseText(el)
        return parsed
    
    for node in nodes:
        attrs = parseAttributes(node)
        id = attrs["id"]
        data = parseData(node)
        graphNodes[id] = data
    
    for edge in edges:
        attrs = parseAttributes(edge)
        source, target = attrs["source"], attrs["target"]
        data = parseData(edge)
        graphEdges[source, target].append(data)
        
    allData = reduce(list.__add__, graphEdges.values(), [])
    edgeTypes = set([int(data["networkGroupId"]) for data in allData])
    groupId2int = dict(zip(edgeTypes, range(len(edgeTypes))))
    groupId2groupCode = dict([(int(data["networkGroupId"]), str(data["networkGroupCode"])) for data in allData])
    graphNode2nodeNumber = dict(zip(graphNodes, range(len(graphNodes))))
    
    import Orange
    graph = Orange.network.Graph()
    for id, data in graphNodes.items():
        graph.add_node(graphNode2nodeNumber[id],
                       original_id=str(id),
                       symbol=data["symbol"],
                       score=float(data["score"]))
         
    graph.add_nodes_from(sorted(graphNode2nodeNumber.values()))
    
    edgeWeights = []
    for (source, target), edge_data in graphEdges.items():
        edgesDefined = [None] * len(edgeTypes)
        for data in edge_data:
            networkGroupId = int(data["networkGroupId"])
            edgeInd = groupId2int[networkGroupId]
            edgesDefined[edgeInd] = float(data["weight"])
            graph.add_edge(graphNode2nodeNumber[source], 
                           graphNode2nodeNumber[target],
                           weight=float(data["weight"]),
                           networkGroupId=networkGroupId)
            
        edgesDefined = [0 if w is None else w for w in edgesDefined]
        edgeWeights.append(edgesDefined)
        
        
    nodedomain = orange.Domain([orange.StringVariable("label"),
                                orange.StringVariable("id"),
                                orange.FloatVariable("score"),
                                orange.StringVariable("symbol"),
                                orange.StringVariable("go"),
                                orange.EnumVariable("source", values=["true", "false"])], None)
    
    edgedomain = orange.Domain([orange.FloatVariable("u"),
                                orange.FloatVariable("v")] +\
                               [orange.FloatVariable("weight_%s" % groupId2groupCode[id]) for id in edgeTypes],
                               None)
    
    node_items = graphNodes.items()
    node_items = sorted(node_items, key=lambda t: graphNode2nodeNumber[t[0]])
    
    nodeitems = orange.ExampleTable(nodedomain,
                  [[str(node["symbol"]), str(id), float(node["score"]),
                    str(node["symbol"]), str(node["go"]), str(node["source"])]\
                     for id, node in node_items])
    
    edgeitems = orange.ExampleTable(edgedomain,
                  [[str(graphNode2nodeNumber[source] + 1), 
                    str(graphNode2nodeNumber[target] + 1)] + weights \
                   for ((source, target), _), weights in zip(graphEdges.items(), edgeWeights)])
        
    graph.set_items(nodeitems)
    graph.set_links(edgeitems)
    
    return graph

def parseValidationResponse(dom):
    def getData(node):
        data = []
        for c in node.childNodes:
            if c.nodeType == node.TEXT_NODE:
                data.append(c.data)
                
        return " ".join([d.strip() for d in data])
        
    def getStrings(node):
        strings = []
        for string in node.getElementsByTagName("string"):
            strings.append(getData(string))
        return strings
    errorCode = dom.getElementsByTagName("errorCode")[0]
    errorCode = getData(errorCode)
    invalidSymbols = getStrings(dom.getElementsByTagName("invalidSymbols")[0])
    geneIds = getStrings(dom.getElementsByTagName("geneIds")[0])
    
    return errorCode, invalidSymbols, geneIds
    

from HTMLParser import HTMLParser

class NetworkGroup(object):
    """ Network group descriptor
    """
    def __init__(self):
        self.weight = ""
        self.networks = []
        self.name = ""
        self.id = ""


class Network(object):
    """ Source network descriptor
    """
    
    def __init__(self):
        self.weight = ""
        self.name = ""
        self.id = ""
        self.description = ""
        
        
class _NetworkTabParser(HTMLParser):
    """ Parses the "Network" tab from the GeneMANIA HTML pages 
    """
    _RE_GROUP_ID = re.compile(r"networkGroup(\d+)")
    _RE_GROUP_WEIGHT_ID = re.compile(r"networkGroupWeight(\d+)")
    _RE_GROUP_NAME_ID = re.compile(r"networkGroupName(\d+)")
    
    _RE_NETWORK_ID = re.compile(r"network(\d+)")
    _RE_NETWORK_WEIGHT_ID = re.compile(r"networkWeight(\d+)")
    _RE_NETWORK_NAME_ID = re.compile(r"networkName(\d+)")
    _RE_NETWORK_DESCRIPTION_ID = re.compile("networkDescription(\d+)")
    
    
    def __init__(self, *args, **kwargs):
        HTMLParser.__init__(self)
        self.networkGroups = []
        self.networks = {}
        
        self.currentGroup = None
        self.currentNetwork = None
        
        self.data_handler = None
        
    def handle_start_group(self, tag, attrs):
        """ Handle '<li class=... id="networkGroup%i">'
        """
        self.currentGroup = NetworkGroup()
        self.currentGroup.id = attrs.get("id")
        
        self.networkGroups.append(self.currentGroup)
        
        
    def handle_start_group_weight(self, tag, attrs):
        """ Handle '<span tooltip="..." id="networkGroupWeight%i">'
        """
        self.data_handler = self.handle_group_weight_data
        
    def handle_group_weight_data(self, data):
        self.currentGroup.weight += data
        
    def handle_end_group_weight(self, tag):
        self.data_handler = None
        
    def handle_start_group_name(self, tag, attrs):
        """ Handle '<div class="network_name" id="networkGroupName%i">'
        """
        self.data_handler = self.handle_group_name_data
        
    def handle_group_name_data(self, data):
        self.currentGroup.name += data
        
    def handle_start_network(self, tag, attrs):
        """ Handle '<li class="checktree_network" id="network%i">'
        """
        self.currentNetwork = Network()
        self.currentNetwork.id = attrs.get("id")
        
        self.currentGroup.networks.append(self.currentNetwork)
        
    def handle_start_network_weight(self, tag, attrs):
        """ Handle '<span tooltip="..." id="networkWeight%i">'
        """
        self.data_handler = self.handle_network_weight_data
        
    def handle_network_weight_data(self, data):
        self.currentNetwork.weight += data
        
    def handle_start_network_name(self, tag, attrs):
        """ Handle '<div class="network_name" id="networkName%i">'
        """
        self.data_handler = self.handle_network_name_data
        
    def handle_network_name_data(self, data):
        self.currentNetwork.name += data
        
    def handle_start_network_description(self, tag, attrs):
        """ Handle '<div class="text" id="networkDescription%i">'
        """
        self.data_handler = self.handle_network_description_data
        
    def handle_network_description_data(self, data):
        self.currentNetwork.description += data
        
    def handle_data(self, data):
        if self.data_handler:
            self.data_handler(data)
    
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "li" and self._RE_GROUP_ID.search(attrs.get("id", "")):
            self.handle_start_group(tag, attrs)
        elif tag == "span" and self._RE_GROUP_WEIGHT_ID.search(attrs.get("id", "")):
            self.handle_start_group_weight(tag, attrs)
        elif tag == "div" and self._RE_GROUP_NAME_ID.search(attrs.get("id", "")):
            self.handle_start_group_name(tag, attrs)
        elif tag == "li" and self._RE_NETWORK_ID.search(attrs.get("id", "")):
            self.handle_start_network(tag, attrs)
        elif tag == "span" and self._RE_NETWORK_WEIGHT_ID.search(attrs.get("id", "")):
            self.handle_start_network_weight(tag, attrs)
        elif tag == "div" and self._RE_NETWORK_NAME_ID.search(attrs.get("id", "")):
            self.handle_start_network_name(tag, attrs)
        elif tag == "div" and self._RE_NETWORK_DESCRIPTION_ID.search(attrs.get("id", "")):
            self.handle_start_network_description(tag, attrs)
        else:
            HTMLParser.handle_starttag(self, tag, attrs)
            
    def handle_endtag(self, tag):
        self.data_handler = None
            

def parsePage(html):
    parser = _NetworkTabParser()
    parser.feed(html)
    return parser.networkGroups
    

def retrieve(org=None, genes=[], m="automatic", r=10):
    """ A helper function, same as Connection().retrive(*args, **kwargs)
    """
    return Connection().retrieve(org, genes, m, r)


"""
======================
PPI Database interface
======================

"""


import sqlite3
import csv
import os
import posixpath

from contextlib import contextmanager
import StringIO

@contextmanager
def finishing(obj):
    """ Calls obj.finish() on context exit.
    """
    yield obj
    obj.finish()

def guess_size(fileobj):
    try:
        if isinstance(fileobj, file):
            return os.fstat(fileobj.fileno()).st_size
        elif isinstance(fileobj, StringIO.StringIO):
            pos = fileobj.tell()
            fileobj.seek(0, 2)
            length = fileobj.tell() - pos
            fileobj.seek(pos, 0)
            return length
        elif isinstance(fileobj, urllib.addinfourl):
            length = fileobj.headers.get("content-length", None)
            return length
    except Exception, ex:
        pass


def copyfileobj(src, dst, buffer=2**10, content_len=None, progress=None):
    count = 0
    if content_len is None:
        content_len = guess_size(src) or sys.maxint
    while True:
        data = src.read(buffer)
        dst.write(data)
        count += len(data)
        if progress:
            progress(100.0 * count / content_len)
        if not data:
            break
            
            
def wget(url, directory=".", dst_obj=None, progress=None):
    """
    .. todo:: Move to Orange.misc
    
    """
    stream = urllib2.urlopen(url)
    length = stream.headers.get("content-length", None)
    if length is None:
        length = sys.maxint
    else:
        length = int(length)
    
    basename = posixpath.basename(url)
        
    if dst_obj is None:
        dst_obj = open(os.path.join(directory, basename), "wb")
    
    if progress == True:
        from Orange.misc import ConsoleProgressBar
        progress = ConsoleProgressBar("Downloading %r." % basename)
        with finishing(progress):
            copyfileobj(stream, dst_obj, buffer=2**10, content_len=length,
                        progress=progress)
    else:
        copyfileobj(stream, dst_obj, buffer=2**10, content_len=length,
                    progress=progress)
    
import obiPPI
import orngServerFiles

import obiTaxonomy
from collections import namedtuple
from operator import itemgetter
from Orange.misc import lru_cache

GENE_MANIA_INTERACTION_FIELDS = \
    ["gene_a", "gene_b", "weight", "network_name",
     "network_group", "source", "pubmed_id"]
     
GeneManiaInteraction = namedtuple("GeneManiaInteraction",
                                  field_names=GENE_MANIA_INTERACTION_FIELDS
                                 )

import weakref
class Internalizer(object):
    """ A class that acts as the python builtin function ``intern``,
    for as long as it is alive.
    
    .. note:: This is for memory optimization only, it does not affect 
        dict lookup speed.
    
    """
    def __init__(self):
        self._intern_dict = {}
        
    def __call__(self, obj):
        return self._intern_dict.setdefault(obj, obj)
    
class GeneManiaDatabase(obiPPI.PPIDatabase):
    DOMAIN = "PPI"
    SERVER_FILE = "gene-mania-{taxid}.sqlite"
    
    TAXID2NAME = ""
    
    # DB schema
    SCHEMA = """
    table: `genes`
        - `internal_id`: int (pk)
        - `gene_name`: text (preferred name)
        
    table: `synonyms`:
        - `internal_id: int (foreign key `genes.internal_id`)
        - `synonym`: text
        - `source_id`: int
        
    table: `source`:
        - `source_id`: int
        - `source_name`: text
        
    table: `links`:
        - `gene_a`: int (fk `genes.internal_key`)
        - `gene_b`: int (fk `genes.internal_key`)
        - `network_id`: (fk `networks.network_id`)
        - `weight`: real
        
    table: `networks`:
        - `network_id`: int
        - `network_name`: text
        - `network_group`: text
        - `source`: text
        - `pubmed_id`: text
        
    view: `links_annotated`:
        - `gene_name_a`
        - `gene_name_b`
        - `network_name`
        - `network_group`
        - `weight`
        
    """
    
    def __init__(self, taxid):
        self.taxid = taxid
        
    @classmethod
    def common_taxids(self):
        return ["3702", "6239", "7227", "9606", "10090", "10116", "4932"]
    
    def organisms(self):
        """ Return all organism taxids contained in this database.
        
        .. note:: a single taxid is returned (the one used at
            instance initialization)   
        
        """
        return [self.taxid]
    
    def ids(self, taxid=None):
        """ Return all primary ids for `taxid`.
        """
        if taxid is None:
            taxids = self.organisms()
            return reduce(list.__add__, map(self.ids, taxids), [])
        
        con = self._db(taxid)
        cur = con.execute("""\
            SELECT gene_name FROM genes
            """)
        return map(itemgetter(0), cur)
        
    def synonyms(self, id):
        """ Return a list of synonyms for primary `id`.
        """
        con = self._db(self.taxid)
        cur = con.execute("""\
            SELECT synonyms.synonym
            FROM synonyms NATURAL LEFT JOIN genes
            WHERE genes.gene_name=?
            """, (id,))
        return map(itemgetter(0), cur)
        
    def all_edges(self, taxid=None):
        """ Return a list of all edges.
        """
        con = self._db(self.taxid)
        cur = con.execute("""
            SELECT links.gene_a, links.gene_b, links.weight
            FROM links""")
        id_to_name = self._gene_id_to_name()
        return [(id_to_name[r[0]], id_to_name[r[1]], r[2]) \
                for r in cur]
        
    def all_edges_annotated(self, taxid=None):
        """ Return a list of all edges with all available annotations
        """
        con = self._db(self.taxid)
        cur = con.execute("""\
            SELECT links.gene_a, links.gene_b, links.weight, links.network_id
            FROM links""")
        gene_to_name = self._gene_id_to_name()
        network_to_description = self._network_id_to_description()
        res = []
        for gene_a, gene_b, w, n_id in cur:
            n_desc = network_to_description[n_id]
            
            res.append(GeneManiaInteraction(gene_to_name[gene_a],
                            gene_to_name[gene_b], w, *n_desc))
        return res
        
    def edges(self, id1):
        """ Return all edges for primary id `id1`.
        """        
        con = self._db(self.taxid)
        cur = con.execute("""\
            SELECT genes1.gene_name, genes2.gene_name, links.weight
            FROM genes AS genes1  
                JOIN links
                    ON genes1.internal_id=links.gene_a
                JOIN genes AS genes2
                    ON genes2.internal_id=links.gene_b
            WHERE genes1.gene_name=?
            """, (id1,))
        res = cur.fetchall()
        cur = con.execute("""\
            SELECT genes1.gene_name, genes2.gene_name, links.weight
            FROM genes AS genes1  
                JOIN  links
                    ON genes1.internal_id=links.gene_a
                JOIN genes AS genes2
                    ON genes2.internal_id=links.gene_b
            WHERE genes2.gene_name=?
            """, (id1,))
        res += cur.fetchall()
        
        return res
    
    def edges_annotated(self, id=None):
        """ Return a list of annotated edges for primary `id` 
        """
        con = self._db(self.taxid)
        cur = con.execute("""\
            SELECT genes1.gene_name, genes2.gene_name, links.weight,
                   networks.network_name, networks.network_group,
                   networks.source, networks.pubmed_id
            FROM genes AS genes1
                JOIN  links
                    ON genes1.internal_id=links.gene_a
                JOIN genes AS genes2
                    ON genes2.internal_id=links.gene_b
                NATURAL JOIN networks
            WHERE genes1.gene_name=?
            """, (id,))
        res = cur.fetchall()
        cur = con.execute("""\
            SELECT genes1.gene_name, genes2.gene_name, links.weight,
                   networks.network_name, networks.network_group,
                   networks.source, networks.pubmed_id
            FROM genes AS genes1
                JOIN links
                    ON genes1.internal_id=links.gene_a
                JOIN genes AS genes2
                    ON genes2.internal_id=links.gene_b
                NATURAL JOIN networks
            WHERE genes2.gene_name=?
            """, (id,))
        res += cur.fetchall()
        return [GeneManiaInteraction(*r) for r in res]
    
    def search_id(self, name, taxid=None):
        """ Search the database for gene name. Return a list of matching 
        primary ids. Use `taxid` to limit the results to a single organism.
        
        """
        con = self._db(self.taxid)
        cur = con.execute("""\
            SELECT genes.gene_name
            FROM genes NATURAL JOIN synonyms
            WHERE synonyms.synonym=? 
            """, (name,))
        return map(itemgetter(0), cur)
        
    def _db(self, taxid=None):
        """ Return an open sqlite3.Connection object.  
        """
        taxid = taxid or self.taxid
        filename = orngServerFiles.localpath_download("PPI",
                            self.SERVER_FILE.format(taxid=taxid))
        if not os.path.exists(filename):
            raise ValueError("Database is missing.")
        
        return sqlite3.connect(filename)
    
    @lru_cache(maxsize=1)
    def _gene_id_to_name(self):
        """ Return a dictionary mapping internal gene ids to 
        primary gene identifiers.
        
        """
        con = self._db(self.taxid)
        cur = con.execute("SELECT * FROM genes")
        return dict(cur)
    
    @lru_cache(maxsize=1)
    def _network_id_to_description(self):
        """ Return a dictionary mapping internal network ids
        to (name, group, source, pubmed id).
         
        """
        con = self._db(self.taxid)
        cur = con.execute("SELECT * FROM networks")
        return dict((t[0], t[1:]) for t in cur)
    
    #####################################
    # Data download and DB initialization
    #####################################
     
    @classmethod
    def download_data(cls, taxid=None, progress_callback=None):
        """ Download the data for ``taxid`` from the GeneMANIA
        website and initialize the local database.
        
        """
        import tarfile
        
        baseurl = "http://genemania.org/data/current/"
        directory = orngServerFiles.localpath("PPI")
        if taxid is None:
            taxid = cls.common_taxids()
        
        if isinstance(taxid, (list, tuple)):
            taxids = taxid
        else:
            taxids = [taxid]
        for taxid in taxids:
            name = obiTaxonomy.name(taxid)
            name = name.replace(" ", "_")
            
            if progress_callback is None:
                progress = True #orngServerFiles.ConsoleProgressBar("Downloading %r." % filename)
            else:
                progress = progress_callback
            
            filename = name + ".tgz"
            url = baseurl + "networks/" + filename    
            wget(url, directory=directory, progress=progress)
            
            tgz_filename = os.path.join(directory, filename)    
            tgz = tarfile.open(tgz_filename)
            tgz.extractall(directory)
            
            filename = name + ".COMBINED.tgz"
            url = baseurl + "precombined/" + filename
            wget(url, directory=directory, progress=progress)
            
            tgz_filename = os.path.join(directory, filename)
            tgz = tarfile.open(tgz_filename)
            tgz.extractall(directory)
        
            cls.init_db([taxid])
        
    @classmethod
    def init_db(cls, taxid=None):
        """ Init the local data base.
        """
        from functools import partial
        directory = orngServerFiles.localpath("PPI")
        pjoin = partial(os.path.join, directory)
        if taxid is None:
            taxid = cls.common_taxids()
            
        if isinstance(taxid, (list, tuple)):
            for tid in taxid:
                cls.init_db(tid)
            return
                
        if not isinstance(taxid, basestring):
            raise ValueError("wrong taxid")
            
#        taxid = taxids
        name = obiTaxonomy.name(taxid).replace(" ", "_")
        networks = csv.reader(open(pjoin(name, "networks.txt")), delimiter="\t")
        networks.next() # Header
        networks = list(networks)
        
        database = pjoin(cls.SERVER_FILE.format(taxid=taxid))
        with sqlite3.connect(database) as con:
            con.execute("""DROP TABLE IF EXISTS genes""")
            con.execute("""DROP TABLE IF EXISTS synonyms""")
            con.execute("""DROP TABLE IF EXISTS source""")
            con.execute("""DROP TABLE IF EXISTS links""")
            con.execute("""DROP TABLE IF EXISTS networks""")
            
            con.execute("""DROP INDEX IF EXISTS genes_index""")
            con.execute("""DROP INDEX IF EXISTS links_index_a""")
            con.execute("""DROP INDEX IF EXISTS links_index_b""")
            
            con.execute("""\
                CREATE TABLE networks 
                    (network_id INTEGER PRIMARY KEY ASC AUTOINCREMENT,
                     network_name TEXT,
                     network_group TEXT,
                     source TEXT,
                     pubmed_id TEXT
                    )""")
            
            con.executemany("""\
                INSERT INTO networks
                VALUES (?, ?, ?, ?, ?)""", [(i, r[2], r[1], r[3], r[4]) \
                                        for i, r in enumerate(networks)])
            
            con.execute("""\
                CREATE TABLE genes
                    (internal_id INTEGER PRIMARY KEY ASC AUTOINCREMENT,
                     gene_name TEXT
                    )""")
            
            identifiers = csv.reader(open(pjoin(name, "identifier_mappings.txt"), "rb"),
                                    delimiter="\t")
            identifiers.next() # skip header
            identifiers = list(identifiers)
            genes = sorted(set(r[0] for r in identifiers))
            sources = sorted(set(r[2] for r in identifiers))
            
            con.executemany("""\
                INSERT INTO genes
                VALUES (?, ?)""", enumerate(genes))
            
            con.execute("""\
            CREATE TABLE source
                (source_id INTEGER PRIMARY KEY ASC AUTOINCREMENT,
                 source_name TEXT
                )""")
            
            con.executemany("""\
                INSERT INTO source
                VALUES (?, ?)""", enumerate(sources))
            
            con.execute("""\
                CREATE TABLE synonyms
                    (internal_id INTEGER REFERENCES genes (internal_id),
                     synonym TEXT,
                     source_id INT REFERENCES source (source_id)
                    )""")
            
            gene_to_id = dict((g, i) for i, g in enumerate(genes))
            source_to_id = dict((s, i) for i, s in enumerate(sources))
            con.executemany("""\
                INSERT INTO synonyms
                VALUES (?, ?, ?)""", [(gene_to_id[r[0]], r[1], source_to_id[r[2]])\
                                       for r in identifiers])
            
            con.execute("""\
                CREATE TABLE links
                    (gene_a INTEGER REFERENCES genes (internal_id),
                     gene_b INTEGER REFERENCES genes (internal_id),
                     network_id INTEGER REFERENCES networks (network_id),
                     weight REAL
                     -- , PRIMARY KEY (gene_a, gene_b, network_id)
                    )""")
            
            for i, (filename, group, _, _, _) in enumerate(networks):
                nf  = open(pjoin(name, filename), "rb")
                interactions = csv.reader(nf, delimiter="\t")
                interactions.next() # skip header
                con.executemany("""\
                    INSERT INTO links 
                    VALUES (?, ?, ?, ?)""",
                    [(gene_to_id[r[0]], gene_to_id[r[1]], i, float(r[2])) \
                     for r in interactions]
                )
                
            # Add special combined network entry
            combined_id = len(networks)
            con.execute("""\
                INSERT INTO networks
                VALUES (?, ?, ?, ?, ?)""", 
                (combined_id, "BP_COMBINING", "COMBINED", "GeneMANIA", ""))
            
            # Add the combined network links.
            combined = open(pjoin(name + ".COMBINED", "COMBINED.DEFAULT_NETWORKS.BP_COMBINING.txt"), "rb")
            combined = csv.reader(combined, delimiter="\t")
            combined.next()
            con.executemany("""\
                INSERT INTO links
                VALUES (?, ?, ?, ?)""",
                    ((gene_to_id[r[0]], gene_to_id[r[1]], combined_id, float(r[2])) \
                     for r in combined))
            
            
            con.execute("""
                CREATE VIEW IF NOT EXISTS links_annotated
                AS SELECT genes1.gene_name AS gene_name_a,
                          genes2.gene_name AS gene_name_b,
                          links.weight,
                          networks.network_name,
                          networks.network_group,
                          networks.source,
                          networks.pubmed_id
                   FROM  genes AS genes1
                        JOIN links 
                              ON genes1.internal_id=links.gene_a
                        JOIN genes AS genes2
                              ON links.gene_b=genes2.internal_id
                        JOIN networks
                              ON links.network_id=networks.network_id
                    """)
            
            
            con.execute("""\
                CREATE INDEX IF NOT EXISTS genes_index ON genes (gene_name)
                """)
            con.execute("""\
                CREATE INDEX IF NOT EXISTS links_index_a ON links (gene_a)
                """)
            con.execute("""\
                 CREATE INDEX IF NOT EXISTS links_index_b ON links (gene_b)
                """)
        
            
if __name__ == "__main__":
    retrieve("9606", [ 'MRE11A', 'RAD51', 'MLH1', 'MSH2', 'DMC1', 'RAD51AP1', 'RAD50', 'MSH6', 'XRCC3', 'PCNA', 'XRCC2' ])
