// PDF Export Modal Functions
function showPdfExportModal() {
    document.getElementById('pdfExportModal').style.display = 'block';
    
    // Populate date fields with current filter values
    const urlParams = new URLSearchParams(window.location.search);
    const currentStartDate = urlParams.get('start_date') || '';
    const currentEndDate = urlParams.get('end_date') || '';
    
    if (currentStartDate) {
        document.getElementById('trendsStartDate').value = currentStartDate;
        document.getElementById('aspectsStartDate').value = currentStartDate;
    }
    if (currentEndDate) {
        document.getElementById('trendsEndDate').value = currentEndDate;
        document.getElementById('aspectsEndDate').value = currentEndDate;
    }
}

function closePdfExportModal() {
    document.getElementById('pdfExportModal').style.display = 'none';
}

function exportPdfWithOptions() {
    const includeAspects = document.getElementById('includeAspects').checked;
    const includeReviews = document.getElementById('includeReviews').checked;

    // Build URL with options
    let url = `/export-pdf`;
    const params = new URLSearchParams();
    
    // Handle aspects date range
    if (includeAspects) {
        params.append('include_aspects', '1');
        const aspectsAllTime = document.getElementById('aspectsAllTime').checked;
        if (aspectsAllTime) {
            params.append('aspects_all_time', '1');
        } else {
            const aspectsStartDate = document.getElementById('aspectsStartDate').value;
            const aspectsEndDate = document.getElementById('aspectsEndDate').value;
            if (aspectsStartDate) params.append('start_date', aspectsStartDate);
            if (aspectsEndDate) params.append('end_date', aspectsEndDate);
        }
    }
    
    // Handle reviews with count
    if (includeReviews) {
        params.append('include_reviews', '1');
        const reviewCount = document.querySelector('input[name="reviewCount"]:checked');
        if (reviewCount) {
            params.append('review_count', reviewCount.value);
        }
    }
    
    if (params.toString()) {
        url += '?' + params.toString();
    }

    // Redirect to download
    window.location.href = url;
    closePdfExportModal();
}

// Close modal when clicking outside
window.addEventListener('click', function(event) {
    const modal = document.getElementById('pdfExportModal');
    if (event.target == modal) {
        closePdfExportModal();
    }
});

function toggleAllOptions(checkbox) {
    const options = document.querySelectorAll('.pdf-option');
    options.forEach(option => {
        option.checked = checkbox.checked;
    });
}

// Update Select All checkbox when individual options change
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.pdf-option').forEach(option => {
        option.addEventListener('change', function() {
            const allChecked = Array.from(document.querySelectorAll('.pdf-option')).every(opt => opt.checked);
            document.getElementById('selectAll').checked = allChecked;
        });
    });
    
    // Show/hide sub-options when checkboxes are toggled
    document.getElementById('includeAspects').addEventListener('change', function() {
        document.getElementById('aspectsDateRange').style.display = this.checked ? 'block' : 'none';
    });
    
    document.getElementById('includeReviews').addEventListener('change', function() {
        document.getElementById('reviewCountSelector').style.display = this.checked ? 'block' : 'none';
    });
    
    // Disable/enable date inputs when "All time" is checked
    document.getElementById('aspectsAllTime').addEventListener('change', function() {
        const disabled = this.checked;
        document.getElementById('aspectsStartDate').disabled = disabled;
        document.getElementById('aspectsEndDate').disabled = disabled;
        if (disabled) {
            document.getElementById('aspectsStartDate').style.opacity = '0.5';
            document.getElementById('aspectsEndDate').style.opacity = '0.5';
        } else {
            document.getElementById('aspectsStartDate').style.opacity = '1';
            document.getElementById('aspectsEndDate').style.opacity = '1';
        }
    });
});
