// Auto-refresh for active tasks
function updateActiveTasks() {
    const taskRows = document.querySelectorAll('#active-tasks tr');
    if (taskRows.length === 0) return;

    // Get all task IDs
    const taskIds = Array.from(taskRows).map(row => row.dataset.taskId);
    
    // Fetch updated task data
    fetch('/api/tasks')
        .then(response => response.json())
        .then(tasks => {
            tasks.forEach(task => {
                const row = document.querySelector(`tr[data-task-id="${task.task_id}"]`);
                if (!row) return;

                // Update status
                const statusCell = row.querySelector('.task-status');
                if (statusCell) statusCell.textContent = task.status;

                // Update progress bar
                const progressBar = row.querySelector('.progress-bar');
                if (progressBar) {
                    progressBar.style.width = `${task.progress}%`;
                    progressBar.setAttribute('aria-valuenow', task.progress);
                    progressBar.textContent = `${task.progress}%`;
                }

                // Update estimated time
                const timeCell = row.querySelector('.estimated-time');
                if (timeCell) {
                    if (task.estimated_time > 0) {
                        timeCell.textContent = `${task.estimated_time} seconds`;
                    } else {
                        timeCell.textContent = 'Calculating...';
                    }
                }

                // If task is completed or failed, refresh the page to show it in the completed section
                if (task.status === 'completed' || task.status === 'failed') {
                    window.location.reload();
                }
            });
        })
        .catch(error => console.error('Error updating tasks:', error));
}

// Update every 3 seconds
setInterval(updateActiveTasks, 3000);

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});