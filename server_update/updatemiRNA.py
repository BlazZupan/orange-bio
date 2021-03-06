
from common import *

import urllib
import re
from io import StringIO
import zipfile

import Orange.bio.obiTaxonomy as tax
from Orange.bio.obimiRNA import toTaxo

def fastprint(filename,mode,what):
    
    file = open(filename,mode)
    file.write(what)
    file.close()
    

def sendMail(subject):
    print "SHOULD MAIL:", subject
        
def format_checker(content):
    
    if len(re.findall('(ID.*?)ID',content.replace('\n',''))):        
        return True
    else:
        sendMail('Uncorrect format of miRBase data-file.')        
        return False

IDpat = re.compile('ID\s*(\S*)\s*standard;')
ACpat = re.compile('AC\s*(\S*);')
RXpat = re.compile('RX\s*PUBMED;\s(\d*).')
FT1pat = re.compile('FT\s*miRNA\s*(\d{1,}\.\.\d{1,})')
FT2pat = re.compile('FT\s*/accession="(MIMAT[0-9]*)"')
FT3pat = re.compile('FT\s*/product="(\S*)"')
SQpat = re.compile('SQ\s*(.*other;)')
seqpat = re.compile('\s*([a-z\s]*)\s*\d*')


    
def get_intoFiles(path, data_webPage):
    
    sections = data_webPage.split('//\n')
    sections.pop()
    
    files = []
    os.system('rm %s/*_sections.txt' % path)
    
    for s in sections:
        org = str(re.findall('ID\s*(\S*)\s*standard;',s.splitlines()[0])[0]).split('-')[0]
        fastprint(os.path.join(path,'%s_sections.txt' % org),'a',s+'//\n')
        
        if not('%s_sections.txt' % org) in files:
            files.append('%s_sections.txt' % org)
            
    content = '\n'.join(list(set(files)))    
    fastprint(os.path.join(path,'fileList.txt'),'w',content)
            
    return os.path.join(path,'fileList.txt')
    
            
        
def miRNA_info(path,object,org_name):
    
    address = os.path.join(path,'%s' % object)
    prefix = str(re.findall('(\S*)_sections\.txt',object)[0])
    
    try:
        data_webPage = urllib.urlopen(address).read()
    except IOError:
        print "miRNA_info Error: Check the web-address."
    
    if data_webPage == []:
        sendMail('Cannot read %s ' % address)
    else:
        format_checker(data_webPage)
            
        print 'I have read: %s' % address
        sections = data_webPage.split('//\n')
        sections.pop()
        print 'Sections found: ', str(len(sections))
            
        num_s = 0
        
        ### files to write        
        fastprint(os.path.join(path,'%s_premiRNA.txt' % prefix),'w','preID'+'\t'+'preACC'+'\t'+'preSQ'+'\t'+'matACCs'+'\t'+'pubIDs'+'\t'+'clusters'+'\t'+'web_addr'+'\n')
        fastprint(os.path.join(path,'%s_matmiRNA.txt' % prefix),'w','matID'+'\t'+'matACC'+'\t'+'matSQ'+'\t'+'pre_forms'+'\t'+'targets'+'\n')
        
        dictG = {}
        dictP = {}
            
        for s in sections:
            num_s = num_s+1
            print 'section: ', num_s, '/', str(len(sections)),
                            
            pubIDs = []
            matIDs = ''
            matACCs = ''
            preSQ=[]
            
            my_ids =[]
            my_accs=[]
            my_locs=[] # if it's [61..81] you have to take from 60 to 81.
            
            rows = s.splitlines()
                
            for r in rows:
                
                if r[0:2] == 'ID':
                    preID = str(IDpat.findall(r)[0])
                    print preID
                        
                elif r[0:2] == 'AC':
                    preACC = str(ACpat.findall(r)[0])
                    web_addr = 'http://www.mirbase.org/cgi-bin/mirna_entry.pl?acc=%s' % preACC
                        
                elif r[0:2] == 'RX' and not(RXpat.findall(r)==[]):
                    pubIDs.append(str(RXpat.findall(r)[0]))

                elif r[0:2]=='FT' and not(FT1pat.findall(r)==[]):
                    loc_mat = str(FT1pat.findall(r)[0])
                        
                    if not(loc_mat==[]):
                         my_locs.append(loc_mat)
                
                elif r[0:2]=='FT' and not(FT2pat.findall(r)==[]):
                     mat_acc = str(FT2pat.findall(r)[0])
                        
                     if matACCs == '':
                         matACCs = mat_acc
                     else:
                         matACCs = matACCs + ',' + mat_acc
                            
                     if not(mat_acc == []):
                         my_accs.append(mat_acc)    
                                
                elif r[0:2]=='FT' and not(FT3pat.findall(r)==[]):
                     mat_id = str(FT3pat.findall(r)[0])
                        
                     if matIDs == '':
                         matIDs = mat_id
                     else:
                         matIDs = matIDs + ',' + mat_id     
                        
                     if not(mat_id == []):
                         my_ids.append(mat_id)
                                          
                elif r[0:2]=='SQ':
            
                     preSQ_INFO = str(SQpat.findall(r)[0])
                     seq = 'on'
            
                elif r[0:2]=='  ' and seq == 'on':
                     preSQ.append(str(seqpat.findall(r)[0]).replace(' ',''))
                     
            ### cluster search
            clusters = ''
            try:
                mirna_page = urllib.urlopen('http://www.mirbase.org/cgi-bin/mirna_entry.pl?acc=%s' % preACC).read()
            except IOError:
                print "miRNA_info Error: Check the address for the miRNA page."
                pass
            
            clust_check = re.findall('<td class="\S*">(Clustered miRNAs)</td>',mirna_page)
                
            if clust_check != [] and str(clust_check[0]) == 'Clustered miRNAs':    
                 clusters = ','.join(re.findall('<td><a href="/cgi-bin/mirna_entry.pl\?acc=MI\d*">(\S*?)</a></td>',mirna_page))
                      
            if clusters == '':
                clusters = 'None'
            
            ### before printing:       
            if pubIDs == []:
                 pubIDs = 'None'
            else:
                pubIDs = ','.join(pubIDs)
            
            preSQ = ''.join(preSQ)
            
            fastprint(os.path.join(path,'%s_premiRNA.txt' % prefix),'a',preID+'\t'+preACC+'\t'+preSQ+'\t'+matACCs+'\t'+pubIDs+'\t'+clusters+'\t'+web_addr+'\n')
                
            for tup in zip(my_ids, my_accs, my_locs):
                
                [start,stop] = tup[2].split('..')
                
                if not(tup[0] in dictG):
                    dictG[tup[0]]=[]
                
                dictG[tup[0]] = [tup[1],preSQ[int(start)-1:int(stop)]]
                
                if not(tup[0] in dictP):
                    dictP[tup[0]]=[]
                
                dictP[tup[0]].append(preID)
                
        for k,v in dictG.items():                
            pre_forms = ','.join(dictP[k]) 
            
            ### targets
            targets = 'None'
            if k in TargetScanLib:
                targets = ','.join(TargetScanLib[k])
           
            fastprint(os.path.join(path,'%s_matmiRNA.txt' % prefix),'a',k+'\t'+v[0]+'\t'+v[1]+'\t'+pre_forms+'\t'+targets+'\n')
        
            
        return [os.path.join(path,'%s_matmiRNA.txt' % prefix), os.path.join(path,'%s_premiRNA.txt' % prefix)]



##############################################################################################################################################################
##############################################################################################################################################################

path = os.path.join(environ.buffer_dir, "tmp_miRNA")
print 'path: ', path

serverFiles = sf_server

try:
    os.mkdir(path)
except OSError:
    pass

org_taxo = [tax.name(id) for id in tax.common_taxids()]

### targets library from TargetScan

try:
    tarscan_url = 'http://www.targetscan.org//vert_50//vert_50_data_download/Conserved_Site_Context_Scores.txt.zip'
    
    zf = zipfile.ZipFile(StringIO(urllib.urlopen(tarscan_url).read()))
    arch = zf.read(zf.namelist()[0]).splitlines()[1:]
    arch.pop()
    mirnas = [a.split('\t')[3] for a in arch]
    gene_ids = [a.split('\t')[1] for a in arch]
    
    TargetScanLib = {}
    for m,t in zip(mirnas,gene_ids):
        if not(m in TargetScanLib):
            TargetScanLib[m] = []
        if not(t in TargetScanLib[m]):           
            TargetScanLib[m].append(t)
except IOError:
    sendMail('Targets not found on: %s' % tarscan_url)    

### miRNA library form miRBase
print "\nBuilding miRNA library..."
address = 'ftp://mirbase.org/pub/mirbase/CURRENT/miRNA.dat.gz'
flag = 1
try:
    data_webPage = gzip.GzipFile(fileobj=StringIO(urllib.urlopen(address).read())).read()
except IOError:
    flag = 0
    sendMail('Database file of miRNAs not found on: %s' % address)
     
if flag:

    orgs = [re.findall('ID\s*(\S+?)-\S*\s*standard;',l)[0] for l in data_webPage.splitlines() if l[:2]=='ID']
    des = [re.findall('DE\s*(.*)\s\S*.*\sstem[\s|-]loop',l)[0] for l in data_webPage.splitlines() if l[:2]=='DE']

    assert len(orgs) == len(des)

    orgs_des = dict(zip(orgs, des))

    file_org = get_intoFiles(path,data_webPage)
    
    miRNA_path = os.path.join(path,'miRNA.txt')
    print 'miRNA file path: %s' % miRNA_path
    premiRNA_path = os.path.join(path,'premiRNA.txt')
    print 'pre-miRNA file path: %s' % premiRNA_path
    
    fastprint(miRNA_path,'w','matID'+'\t'+'matACC'+'\t'+'matSQ'+'\t'+'pre_forms'+'\t'+'targets'+'\n')
    fastprint(premiRNA_path,'w','preID'+'\t'+'preACC'+'\t'+'preSQ'+'\t'+'matACCs'+'\t'+'pubIDs'+'\t'+'clusters'+'\t'+'web_addr'+'\n')
    
    for fx in [l.rstrip() for l in open(file_org).readlines()]:
        if orgs_des[fx.split('_')[0]] in org_taxo:
            
            end_files = miRNA_info(path, fx,orgs_des[fx.split('_')[0]])
            
            for filename in end_files:
                print "Now reading %s..." % filename            
                org = re.findall('/(\S{3,4})_\S{3}miRNA\.txt',filename)[0]
                type_file = re.findall(org+'_(\S*)miRNA\.txt',filename)[0]
                label = re.findall('/(\S{3,4}_\S{3}miRNA?)\.txt',filename)[0]
    
                org_taxid = str(toTaxo.get(org))
                org = tax.name(str(toTaxo.get(org)))
                
                if type_file == 'mat':
                    serverFiles.upload("miRNA", label, filename, title="miRNA: %s mature form" % org, tags=["miRNA"] + tax.shortname(org_taxid))
                    serverFiles.unprotect("miRNA", label)
                    print '%s mat uploaded' % org
                    
                    for file_line in open(filename).readlines()[1:]:
                        fastprint(miRNA_path,'a',file_line)                 
                    
                elif type_file == 'pre':
                    serverFiles.upload("miRNA", label, filename, title="miRNA: %s pre-form" % org, tags=["miRNA"] + tax.shortname(org_taxid))
                    serverFiles.unprotect("miRNA", label)
                    print '%s pre uploaded' % org
                    
                    for file_line in open(filename).readlines()[1:]:
                        fastprint(premiRNA_path,'a',file_line)
                        
                else:
                    print 'Check the label.'
    
    serverFiles.upload("miRNA", "miRNA.txt", miRNA_path, title="miRNA: miRNA library", tags=["miRNA"] )
    serverFiles.unprotect("miRNA", "miRNA.txt")
    print '\nmiRNA.txt uploaded'
    
    serverFiles.upload("miRNA", "premiRNA.txt", premiRNA_path, title="miRNA: pre-form library", tags=["miRNA"])
    serverFiles.unprotect("miRNA", "premiRNA.txt")
    print 'premiRNA.txt uploaded\n'
else:
    print "Check the address of miRNA file on %s" % address

