import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from evaluation.catalog import ROWS,login
from helpline.__main__ import local_desk
from helpline.desk import Desk,parse_day
from helpline.policy import PRIVATE,SAFE,charge,classify,safe_output,uk_advisory,uk_clearing_date
from helpline.tools import fresh,lookup_account,quote_balance,quote_statement,check_limit,complete_handoff

class Invariants(unittest.TestCase):
    def test_no_private_values_from_unverified_tools(self):
        s=fresh()
        for intent,func,args in (("balance",quote_balance,()),("statement",quote_statement,("3","digital")),("limit",check_limit,("2","Instant Pay","2026-11-10"))):
            s["intent_tag"]=intent
            self.assertEqual({},func(s,ROWS,*args))
        self.assertEqual({},lookup_account(s,ROWS));self.assertEqual({},complete_handoff(s))
    def test_no_second_dispatch_across_simultaneous_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            def submit(_):
                with local_desk(Path(tmp)) as d:
                    for t in login(0)+["statement","3","yes","digital"]: d.turn(t)
                    return d.s["handoff"]["reason"]
            with ThreadPoolExecutor(2) as p:
                self.assertCountEqual(p.map(submit,range(2)),["already_sent","service_complete"])
            events=[json.loads(l) for l in (Path(tmp)/"handoffs.jsonl").read_text().splitlines()]
            self.assertEqual(len(events),2)
            for event in events:self.assertEqual(set(event),{"destination","intent","channel","reason"})
    def test_final_handoff_once(self):
        events=[];d=Desk(ROWS,callback=events.append)
        d.turn("representative"); self.assertEqual(d.turn("balance"),"This call has ended.")
        self.assertEqual(len(events),1)
    def test_two_retries_can_succeed(self):
        d=Desk(ROWS)
        turns=["HT4102","1993-06-15","0042","yes","1993-06-16","yes","1993-06-14","yes"]
        for turn in turns: d.turn(turn)
        self.assertTrue(d.s["verified"]);self.assertEqual(d.s["attempts"],0)
    def test_verification_retry_only_reasks_the_failed_field(self):
        d=Desk(ROWS)
        for turn in ["HT4102","1993-06-15","0042","yes"]: reply=d.turn(turn)
        self.assertIn("date of birth",reply.lower())
        self.assertEqual(d.s["stage"],"dob")
        self.assertEqual((d.s["candidate"],d.s["ending"]),("HT4102","0042"))
        d.turn("1993-06-14")
        self.assertEqual(d.s["stage"],"confirm_id")
        d.turn("yes")
        self.assertTrue(d.s["verified"])
    def test_unknown_customer_id_is_a_technical_handoff(self):
        d=Desk(ROWS)
        for turn in ("HT0000","1993-06-14","0042","yes"): reply=d.turn(turn)
        self.assertIn("couldn't retrieve",reply.lower())
        self.assertEqual(d.s["handoff"]["reason"],"lookup")
    def test_frozen_statement_is_not_automated(self):
        d=Desk(ROWS)
        for turn in login(3)+["statement"]: reply=d.turn(turn)
        self.assertIn("colleague",reply.lower())
        self.assertEqual(d.s["handoff"]["reason"],"status")
        self.assertNotIn("fee",reply.lower())
    def test_lookup_exception_reaches_human(self):
        class Unavailable:
            def __iter__(self):
                raise TimeoutError("offline")
        d=Desk(ROWS)
        for turn in login(0):d.turn(turn)
        d.rows=Unavailable()
        self.assertIn("couldn't retrieve",d.turn("balance"))
        self.assertEqual(d.s["handoff"]["reason"],"lookup")
    def test_malformed_verification_budget(self):
        d=Desk(ROWS)
        for t in ("HT4102","not a date","not a date","not a date"):reply=d.turn(t)
        self.assertIn("person",reply)
        self.assertEqual(d.s["handoff"]["reason"],"verification")
    def test_numeric_boundaries(self):
        for v in ("0","-1","NaN","Infinity"):self.assertEqual(charge(v,"digital"),{"error":"invalid"})
        self.assertEqual(charge("3.00001","digital")["fee"],100)
        self.assertEqual(charge("36.01","printed"),{"error":"archive"})
    def test_sensitive_forms_and_money(self):
        for t in ("My Aadhaar is 0000 0000 0000","PIN one two three four","four five three two "*4):self.assertEqual(classify(t),"private")
        self.assertEqual(safe_output("Your account ending is 12345678."),SAFE)
        self.assertEqual(safe_output("The charge is INR 400.",(100,)),SAFE)
        self.assertEqual(safe_output("The fee is 100 rupees.",(100,)),"The fee is 100 rupees.")
    def test_dates_and_unavailable_calendar(self):
        for t in ("June fourteenth nineteen ninety three","the fourteenth of June 1993","June 14, 1993"):
            self.assertEqual(parse_day(t),"1993-06-14")
        self.assertFalse(parse_day("31 February 2027"))
        self.assertIn("couldn't check",uk_advisory("2034-01-01",{}))
        self.assertIn("cached calendar",uk_advisory("2027-01-01",{}))
        self.assertIn("4 January 2027",uk_advisory("2027-01-01",{}))
        self.assertIn("couldn't check",uk_advisory("2027-01-01",{},fallback={}))
        self.assertEqual(uk_clearing_date("2027-01-01",{}),{"available":True,"date":"2027-01-04","adjusted":True,"source":"cache"})
    def test_sensitive_interruption_does_not_mutate_identity(self):
        d=Desk(ROWS);d.turn("HT4102")
        self.assertEqual(d.turn("my PIN is one two three four"),PRIVATE)
        self.assertEqual(d.s["stage"],"dob")
        self.assertEqual(d.s["dob"],"")

if __name__=="__main__":
    unittest.main()
