import logging
import sys
import uuid

import pandas as pd
import graphviz as gv

log = logging.getLogger(__name__)

filename = 'List of People.xlsx'
sheet_name = 'Sheet1'
xl = pd.ExcelFile(filename)
df = xl.parse(sheet_name)

family_tree = {p._1: p for p in df.itertuples()}
family_tree_columns = df.columns

def spouse_columns():
    cols = []
    for idx, f in enumerate(family_tree_columns, 1):
        if 'Spouse' in f:
            cols.append('_%d' % idx)
    return cols

print('NORM: %s' % str(family_tree[24]))

# 1. Mom + Dad
# 2. Siblings
# 3. Spouse(s)
# 4. Kids

def parents(tree, person_id):
    return [int(tree[person_id].Mother), int(tree[person_id].Father)]

def siblings(tree, person_id):
    return []

def spouses(tree, person_id):
    return [tree[person_id]._asdict()[s] for s in spouse_columns()]

def kids(tree, person_id):
    k = []
    for pid, p in tree.iteritems():
        try:
            if int(p.Father) == person_id or \
               int(p.Mother) == person_id:
                k.append(pid)
        except ValueError as e:
            log.debug(e)
            continue
    return k

def filter_by(tree, person_id):
    if person_id not in tree:
        log.error('%d not in family tree', person_id)
        sys.exit(1)
    nodes = [person_id] + \
           parents(tree, person_id) + \
           siblings(tree, person_id) + \
           spouses(tree, person_id) + \
           kids(tree, person_id)
    return [n for n in nodes if n in tree]

def digraph(tree):
    dot = gv.Digraph(comment='Family Tree')

    def node(idx):
        return 'P-%d' % idx

    def union(pair):
        ordered = sorted(list(pair))
        return 'U-%d-%d' % (ordered[0], ordered[1])

    def union_members(u):
        return [int(v) for v in u.split('-')[1:]]

    # First, organize nodes into generations.
    # Constrain the output graph so that all nodes
    # in the same generation have the same rank.
    generations = {}
    for p in tree.itervalues():
        def get_generation(node):
            for gn, g in generations.iteritems():
                if node in g:
                    return gn
            return None
        candidate_gens = set()
        spouse_gens = [get_generation(s) for s in spouses(tree, p._1)]
        for sg in spouse_gens:
            if sg is not None:
                candidate_gens.add(sg)
        gen = uuid.uuid4()
        if len(candidate_gens) > 1:
            merged_gen = set().union([generations[c] for c in candidate_gens])
            generations[gen] = merged_gen
            for c in candidate_gens:
                del generations[c]
        elif candidate_gens:
            gen = candidate_gens.pop()
        if gen not in generations:
            generations[gen] = []
        generations[gen].append(p._1)

    # Identify all unions in the family tree
    unions = set()
    for p in tree.itervalues():
        for s in spouses(tree, p._1):
            if s in tree:
                unions.add(union((p._1, s)))

    # Declare all our nodes
    # For each spouse pair, make a hidden node to represent their union
    unions_created = set()
    for g in generations.itervalues():
        with dot.subgraph() as s:
            s.attr(rank='same')
            for _id in g:
                p = tree[_id]
                s.node(node(_id), '%d: %s, %s' % (p._1, p.Last, p.First))
                for u in unions:
                    if u in unions_created:
                        continue
                    elif _id in union_members(u):
                        print('---------')
                        print(u)
                        s.node(u, '', shape='circle', height='0.02')
                        unions_created.add(u)

    # Declare edges
    for p in tree.itervalues():
        # Mother / Father
        if p.Mother in tree and p.Father in tree:
            u = union((p.Mother, p.Father))
            dot.edge(u, node(p._1))
        elif p.Mother in tree:
            dot.edge(node(p.Mother), node(p._1))
        elif p.Father in tree:
            dot.edge(node(p.Father), node(p._1))
        # Spouses
        for s in spouse_columns():
            spouse = p._asdict()[s]
            if spouse not in tree:
                continue
            u = union((p._1, spouse))
            members = union_members(u)
            if members[0] == p._1:
                dot.edge(node(p._1), u, arrowhead='none')
            else:
                dot.edge(u, node(p._1), arrowhead='none')
    return dot


logging.basicConfig(level=logging.INFO)

trees = [ None, 1, 24 ]

for t in trees:
    if t is None:
        subtree = family_tree
        filename = 'family_tree_all.gv'
    else:
        log.info('Generating tree for person %d', t)
        subtree = {n: family_tree[n] for n in filter_by(family_tree, t)}
        p = family_tree[t]
        filename = 'family_tree_%s-%s-%s.gv' % (p._1, p.Last, p.First)
    dg = digraph(subtree)
    dg.render(filename, view=False)

