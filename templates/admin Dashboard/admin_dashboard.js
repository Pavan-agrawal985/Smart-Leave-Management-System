document.addEventListener('DOMContentLoaded', () => {
    // 1. Highlight Active Sidebar Link based on current URL
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('nav a');
    
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
        }
    });

    // 2. Action Confirmation (Approve/Reject)
    const actionForms = document.querySelectorAll('form[action*="/leave/"]');
    
    actionForms.forEach(form => {
        form.addEventListener('submit', (e) => {
            const isApprove = form.getAttribute('action').includes('approve');
            const actionText = isApprove ? 'approve' : 'reject';
            
            const confirmed = confirm(`Are you sure you want to ${actionText} this leave request?`);
            
            if (!confirmed) {
                e.preventDefault(); // Stop the form from submitting
            }
        });
    });

    // 3. Sidebar Responsive Toggle (Optional)
    // If you add a hamburger menu icon later, use this:
    const handleResize = () => {
        const sidebar = document.querySelector('.sidebar');
        if (window.innerWidth < 768) {
            sidebar.style.marginLeft = '-260px';
        } else {
            sidebar.style.marginLeft = '0';
        }
    };

    window.addEventListener('resize', handleResize);
    handleResize(); // Initialize on load
});