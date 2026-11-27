from backend.backend_utils.consultation_history_utils import group_consultations

def test_scheduling_links_and_numeric_order():
    def e(id,t,seq=None): return dict(examination_id=id,examination_type=t,status='Completed',follow_up_sequence=seq)
    exams=[e('a','General Consult'),e('b','General Consult'),e('x','Follow-Up Examination',10),e('y','Follow-Up Examination',2),e('z','Follow-Up Examination',6)]
    links=[dict(source_examination_id=p,follow_up_examination_id=c) for p,c in [('a','x'),('a','y'),('b','z')]]
    _,g,o=group_consultations(exams,links)
    assert [v['examination_id'] for v in g['a']]==['y','x']
    assert len(g['b'])==1 and not o

def test_conflicting_links():
    exams=[dict(examination_id=i,examination_type=t,status='Completed') for i,t in [('a','General Consult'),('b','General Consult'),('x','Follow-Up Examination')]]
    _,g,o=group_consultations(exams,[dict(source_examination_id=p,follow_up_examination_id='x') for p in ['a','b']])
    assert len(o)==1 and not any(g.values())
