"""Exercise research continuation through the public dispatcher, without live models."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from adapters.legacy_records import seed_experiment
from types import SimpleNamespace
from unittest.mock import patch

from frontier_research_harness.adapters.frontier_science_workspace import FrontierScienceWorkspace
from frontier_research_harness.adapters.scientific_model_mcp import _call_tool, _list_tools


class ResearchResumeTests(unittest.TestCase):
    def call(self, database, tool_name, **arguments):
        result = asyncio.run(_call_tool(None, SimpleNamespace(name=tool_name, arguments=arguments), database=database))
        self.assertFalse(result.is_error, result.content)
        return json.loads(result.content[0].text)

    def test_reopen_reload_contrary_result_then_revise_understanding(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'research.sqlite3'
            self.call(database, 'save_research', data={'current_understanding': 'A might improve the whole outcome.'})
            with FrontierScienceWorkspace(database) as workspace:
                run = seed_experiment(workspace, name='pulse', model_input={'synthetic': True}, raw_output={'power':12,'cost':30},
                                question='Does improving A increase the cost in B?', provenance=[{'kind': 'synthetic test'}])
            note = self.call(database, 'research_log', operation='append', payload={
                'author': 'CODEX', 'text': 'Unexpected cost: inspect the local mechanism and whole-body effect.',
                'references': [run['experiment_id']]})
            resumed = self.call(database, 'load_research')
            goal = resumed['workspace']['fixed_goal']
            self.assertEqual(goal['optimization_objective']['aggregation'], 'equal_weight_arithmetic_mean')
            self.assertIn('역설계', goal['research_intent'])
            self.assertEqual(goal['research_artifacts']['score_table'], 'docs/SCORECARD.md')
            self.assertTrue(goal['action_boundary'])
            events = resumed['workspace']['recent_activity']['events']
            self.assertEqual(events[0]['id'], note['entry_id'])
            event = next(e for e in events if e['id'] == run['experiment_id'])
            reloaded = json.loads(self.call(database, event['reload']['tool'], **event['reload']['arguments'])['content'])
            self.assertEqual(reloaded['raw_output'], {'power': 12, 'cost': 30})
            self.assertEqual(reloaded['input'], {'synthetic': True})
            self.call(database, 'save_research', data={'current_understanding': 'A has a cross-system cost; its cause is unresolved.'})
            history = self.call(database, 'load_research', sections=['current_understanding'], history_limit=2)
            self.assertEqual(len(history['workspace']['understanding_history']), 2)
            self.assertIn('unresolved', history['workspace']['current_understanding'])

    def test_failed_run_remains_visible_without_becoming_a_finding(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'research.sqlite3'
            with FrontierScienceWorkspace(database) as workspace:
                failed = seed_experiment(workspace, 'pulse', {}, status='FAILED', question='Test failed execution', provenance=[{'kind': 'test'}])
            resumed = self.call(database, 'load_research', sections=['recent_activity'])
            event = resumed['workspace']['recent_activity']['events'][0]
            self.assertEqual(event['status'], 'FAILED')
            self.assertEqual(event['id'], failed['experiment_id'])
            self.assertNotIn('next_question', event)
            self.assertNotIn('score', event)
            with FrontierScienceWorkspace(database) as workspace:
                with self.assertRaisesRegex(ValueError, 'failed experiment'):
                    workspace.save_research({'research_notes': [{
                        'statement': 'This proves A.', 'support_status': 'MODEL_BOUND',
                        'experiment_ids': [failed['experiment_id']]}]})

    def test_activity_is_bounded_read_only_and_exact_notes_remain_retrievable(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'research.sqlite3'
            full_text = '한글 관측 ' * 2000
            for i in range(3):
                self.call(database, 'research_log', operation='append', payload={'author': 'USER', 'text': full_text + str(i)})
            result = self.call(database, 'load_research', sections=['recent_activity'], recent_items=1, max_utf8_bytes=4096)
            self.assertLessEqual(len(json.dumps(result, ensure_ascii=False).encode('utf-8')), 4096)
            activity = result['workspace']['recent_activity']
            self.assertTrue(activity['more_available'])
            event = activity['events'][0]
            self.assertTrue(event['preview_may_be_truncated'])
            exact = self.call(database, event['reload']['tool'], **event['reload']['arguments'])
            self.assertEqual(exact['entries'][0]['record']['text'], full_text + '2')
            with FrontierScienceWorkspace(database) as workspace:
                with self.assertRaisesRegex(ValueError, 'unknown research sections'):
                    workspace.save_research({'recent_activity': {'events': []}})
            explicit = self.call(database, 'load_research', sections=['current_understanding'])
            self.assertNotIn('recent_activity', explicit['workspace'])

    def test_public_schema_advertises_resume_context(self):
        tools = asyncio.run(_list_tools()).tools
        schema = next(t.input_schema for t in tools if t.name == 'load_research')
        self.assertIn('recent_activity', schema['properties']['sections']['items']['enum'])

    def test_whole_goal_evidence_can_be_retained_without_inventing_subtargets(self):
        from tests.adapters.test_frontier_science_workspace import scholarly_evidence
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'research.sqlite3'
            goal_id = self.call(database, 'load_research')['workspace']['fixed_goal']['goal_id']
            evidence = scholarly_evidence(target_ids=[goal_id])
            saved = self.call(database, 'save_evidence', record=evidence)
            resumed = self.call(database, 'load_research', sections=['recent_activity'])
            event = resumed['workspace']['recent_activity']['events'][0]
            exact = self.call(database, event['reload']['tool'], **event['reload']['arguments'])
            self.assertEqual(exact['record']['target_ids'], [goal_id])
            self.assertEqual(event['id'], saved['evidence_id'])
            with FrontierScienceWorkspace(database) as workspace:
                with self.assertRaisesRegex(ValueError, 'unknown target'):
                    workspace.save_evidence(scholarly_evidence(identifier='other', target_ids=['invented-target']))


if __name__ == '__main__':
    unittest.main()
