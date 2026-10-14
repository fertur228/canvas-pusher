"""Explicit read-only Canvas verification; emits schema counts, never academic payloads."""
import asyncio
from datetime import datetime
import json
import logging
import os
from .scanner import ReliableCanvasScanner,ScanFailure

async def check():
    logging.getLogger('httpx').setLevel(logging.WARNING)
    url,token=os.getenv('CANVAS_API_URL'),os.getenv('CANVAS_API_KEY')
    if not url or not token:return {'status':'blocked','missing':'CANVAS_API_URL/CANVAS_API_KEY'}
    scanner=ReliableCanvasScanner(token,url,None)
    try:
        courses=await scanner.get_active_courses()
        assignments,files,announcements=await scanner.scan_all(courses)
    except ScanFailure as error:
        return {'status':'failed','error_code':str(error),'http_status_counts':dict(scanner.http_statuses),
                'requests':scanner.request_count,'pagination_hops':scanner.pagination_hops,
                'mutations':0,'telegram_messages':0,'private_details_omitted':True}
    for row in assignments:
        if row.get('due_at') and datetime.fromisoformat(row['due_at'].replace('Z','+00:00')).tzinfo is None:raise ValueError('naive_deadline')
        if type(row['has_submitted']) is not bool:raise ValueError('invalid_submission_status')
    return {'status':'verified' if not scanner.failures else 'partial_failure','real_canvas_read':True,
            'courses':len(courses),'assignments':len(assignments),'files':len(files),'announcements':len(announcements),
            'failed_scopes':scanner.failures,'requests':scanner.request_count,'pagination_hops':scanner.pagination_hops,'http_status_counts':dict(scanner.http_statuses),'timezone_and_submission_schema_checked':True,'mutations':0,'telegram_messages':0}

def main():
    try:report=asyncio.run(check())
    except Exception:report={'status':'failed','error_code':'canvas_read_or_schema_failed','private_details_omitted':True}
    print(json.dumps(report));raise SystemExit(0 if report['status']=='verified' else 2)
if __name__=='__main__':main()
