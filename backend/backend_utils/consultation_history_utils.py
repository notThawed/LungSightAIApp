# backend_utils/consultation_history_utils.py
from backend.backend_utils.examination_record_utils import finalized_examination_records


def group_consultations(exams, links):
    by_id = {str(e['examination_id']): e for e in exams if e.get('examination_id')}
    eligible = finalized_examination_records(exams)
    roots = [e for e in eligible if str(e.get('examination_type', '')).lower().strip() in ('general consult', 'general consultation')]
    groups = {str(e['examination_id']): [] for e in roots}
    edges = {}
    for link in links:
        child, parent = link.get('follow_up_examination_id'), link.get('source_examination_id')
        if child and parent:
            edges.setdefault(str(child), set()).add(str(parent))
    def resolve(node, seen):
        if node in seen or node not in by_id:
            return None
        if node in groups:
            return node
        parents = set(edges.get(node, ()))
        parent = by_id[node].get('parent_examination_id')
        if parent:
            parents.add(str(parent))
        results = {resolve(p, seen | {node}) for p in parents}
        return next(iter(results)) if len(results) == 1 else None
    orphaned = []
    for e in eligible:
        if 'follow' not in str(e.get('examination_type', '')).lower():
            continue
        root = resolve(str(e.get('examination_id')), set())
        (groups[root] if root else orphaned).append(e)
    def order(e):
        try: seq = int(e.get('follow_up_sequence'))
        except (TypeError, ValueError): seq = 10**9
        return seq, str(e.get('examination_date') or e.get('created_at') or '')
    for items in groups.values(): items.sort(key=order)
    roots.sort(key=lambda e: str(e.get('examination_date') or e.get('created_at') or ''), reverse=True)
    orphaned.sort(key=order)
    return roots, groups, orphaned
