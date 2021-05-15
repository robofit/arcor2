# Lock & Lock Structures

- Lock is used to providing exclusive access to objects. 
  - UI elements (dobot, action point, etc.).
  - Global variables.
- Each lock record requires a lock owner.
- Each UI element must be explicitly locked before editing in RPC code.
  - There are 3 ways to acquire this lock:
     1. Using locking RPC.
     2. Using context lock.
     3. Directly locking object ID using lock methods.
- Access to the lock database (`_locked_object` attribute) should be always done after acquiring `_lock` to access consistent and valid data.
- Locks visible in UI (long-lasting locks mostly acquired by locking RPC) are stored in the `_ui_user_locks` attribute.
  - All those locks must be explicitly maintained when used (e.g. `notify` argument of (un)locking methods)
  - UI is not notified about locks created by the context manager. Such cases last a short time period and it could cause object blinking in AREditor.
- To ensure multiple RPCs can use the same object in a short time period, a `retry` decorator has been implemented. It's used inside of lock context managers and when acquiring exclusive access to lock the database for a wider time period.
- To keep the database clean and always store relevant results, all data related to the released lock must be removed from the database.

### Lock methods

- Lock consists of many methods where approximately half of them are private. In most cases, the private method is used when lock database lock is already acquired.
- To prevent deadlock situation **never use async call inside of critical section**. The best practice is to create a private method without `async` in the function definition.


### Special cases

- There are cases, where the object requires to be locked until an asynchronous call is finished, such as `create_task` or `ensure_future`. For such cases, it's recommended to use context lock with `auto_unlock=False` and `try` + `finally` for the whole asynchronous task, where finally will unlock all objects.
  - When `dry_run` is available for such RPC, it must be also applied in context manager for correct behavior during exceptions.


### User lock maintanance

- Use can generally edit projects and use locks after login.
- When the user logs out with some acquired locks, timeout is executed. After the timeout period all affected locks are released.
  - When user activity is restored, the cleaning task is canceled.
