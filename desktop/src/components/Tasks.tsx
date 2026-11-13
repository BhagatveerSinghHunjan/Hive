import { useCallback, useEffect, useState, type FormEvent } from 'react';
import type { RequestFn, TaskItem } from '../types';

interface TasksProps {
  request: RequestFn;
  refreshKey: number;
  onNotify: (kind: string, title: string, detail?: string) => void;
}

export function TasksScreen({ request, refreshKey, onNotify }: TasksProps) {
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [pending, setPending] = useState(0);
  const [showCompleted, setShowCompleted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [due, setDue] = useState('');
  const [priority, setPriority] = useState('medium');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await request('tasks', { include_completed: showCompleted });
      setTasks(data.tasks ?? []);
      setPending(Number(data.pending ?? 0));
      if (!data.ok) setError(String(data.error ?? 'Tasks unavailable'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [request, showCompleted]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const addTask = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      const value = title.trim();
      if (!value) return;
      setError('');
      try {
        const data = await request('task_add', {
          title: value,
          due: due || null,
          priority,
          notes: '',
        });
        if (!data.ok) {
          setError(String(data.error ?? 'Could not add task'));
          return;
        }
        setTitle('');
        setDue('');
        onNotify('response', 'Task added', value);
        await load();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [due, load, onNotify, priority, request, title]
  );

  const complete = useCallback(
    async (task: TaskItem) => {
      setBusyId(task.task_id);
      setError('');
      try {
        const data = await request('task_complete', { task_id: task.task_id });
        if (!data.ok) {
          setError(String(data.error ?? 'Could not complete task'));
        } else {
          onNotify('response', 'Task completed', task.title);
        }
        await load();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusyId(null);
      }
    },
    [load, onNotify, request]
  );

  return (
    <div className="ops-page">
      <div className="page-head">
        <div>
          <h1>Tasks</h1>
          <p>Follow-ups captured by HIVE. Local by default, with optional Google Tasks sync.</p>
        </div>
        <div className="page-head-actions">
          <span className="pending-pill">{pending} pending</span>
          <button className="ghost-btn" onClick={() => setShowCompleted((value) => !value)}>
            {showCompleted ? 'Hide completed' : 'Show completed'}
          </button>
          <button className="ghost-btn" onClick={() => void load()} disabled={loading}>
            {loading ? 'Loading…' : 'Refresh'}
          </button>
        </div>
      </div>

      {error && <div className="banner banner-error">{error}</div>}

      <form className="task-form card" onSubmit={addTask}>
        <input
          className="text-input"
          placeholder="What needs to happen?"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
        <input
          className="text-input"
          type="date"
          value={due}
          onChange={(event) => setDue(event.target.value)}
        />
        <select
          className="text-input"
          value={priority}
          onChange={(event) => setPriority(event.target.value)}
        >
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <button className="btn btn-approve" type="submit" disabled={!title.trim()}>
          Add task
        </button>
      </form>

      <div className="item-list">
        {tasks.length === 0 && !loading ? (
          <div className="empty">
            <div className="empty-icon">☑</div>
            <h2>No tasks</h2>
            <p>Add one above, or ask HIVE to capture follow-ups from email and meetings.</p>
          </div>
        ) : (
          tasks.map((task) => (
            <article
              key={task.task_id}
              className={`task-row ${task.status === 'done' ? 'task-done' : ''}`}
            >
              <button
                className="task-check"
                disabled={task.status === 'done' || busyId === task.task_id}
                onClick={() => void complete(task)}
                aria-label={task.status === 'done' ? 'Completed' : 'Complete task'}
              >
                {task.status === 'done' ? '✓' : ''}
              </button>
              <div className="task-main">
                <div className="task-title">{task.title}</div>
                {task.notes && <div className="task-notes">{task.notes}</div>}
                <div className="tag-row">
                  <span className={`priority-badge priority-${task.priority ?? 'medium'}`}>
                    {task.priority ?? 'medium'}
                  </span>
                  {task.due && <span className="tag">due {task.due}</span>}
                  {task.source && task.source !== 'local' && <span className="tag">{task.source}</span>}
                </div>
              </div>
            </article>
          ))
        )}
      </div>
    </div>
  );
}
