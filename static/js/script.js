
// Ensure DOM is loaded before running scripts
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
}

function initializeApp() {
    // All your existing script initialization code goes here
    // Make sure all DOM queries happen inside this function
    console.log('App initialized');
}
// API configuration
const API_BASE_URL = 'http://localhost:5000';

// Global variables
let subjects = {};
let courseTypes = [];
let selectedCourseTypes = [];
let userGrades = {};
let clusterPoints = {};
let meanGrade = '';

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    loadSubjects();
    loadCourseTypes();
    setupEventListeners();
});

// Load subjects from API
async function loadSubjects() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/subjects`);
        if (response.ok) {
            subjects = await response.json();
            initializeSubjectInputs();
        } else {
            console.error('Failed to load subjects');
        }
    } catch (error) {
        console.error('Error loading subjects:', error);
    }
}

// Load course types from API
async function loadCourseTypes() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/course-types`);
        if (response.ok) {
            courseTypes = await response.json();
            initializeCourseTypeSelection();
        } else {
            console.error('Failed to load course types');
        }
    } catch (error) {
        console.error('Error loading course types:', error);
    }
}

// Initialize subject inputs
function initializeSubjectInputs() {
    const container = document.getElementById('subjects-container');
    if (!container) return;
    
    container.innerHTML = '';
    
    for (const [code, name] of Object.entries(subjects)) {
        const subjectItem = document.createElement('div');
        subjectItem.className = 'form-group';
        
        subjectItem.innerHTML = `
            <label for="subject-${code}">${name} (${code})</label>
            <select id="subject-${code}" class="subject-grade">
                <option value="">Select Grade</option>
                <option value="A">A</option>
                <option value="A-">A-</option>
                <option value="B+">B+</option>
                <option value="B">B</option>
                <option value="B-">B-</option>
                <option value="C+">C+</option>
                <option value="C">C</option>
                <option value="C-">C-</option>
                <option value="D+">D+</option>
                <option value="D">D</option>
                <option value="D-">D-</option>
                <option value="E">E</option>
            </select>
        `;
        
        container.appendChild(subjectItem);
    }
}

// Initialize cluster inputs
function initializeClusterInputs() {
    const container = document.getElementById('cluster-inputs');
    if (!container) return;
    
    container.innerHTML = '';
    
    for (let i = 1; i <= 20; i++) {
        const cluster = `cluster_${i}`;
        const formGroup = document.createElement('div');
        formGroup.className = 'form-group';
        
        formGroup.innerHTML = `
            <label for="cluster-${cluster}">${cluster}</label>
            <input type="number" id="cluster-${cluster}" min="0" max="100" step="0.1" placeholder="Enter points">
        `;
        
        container.appendChild(formGroup);
    }
}

// Initialize course type selection
function initializeCourseTypeSelection() {
    const container = document.getElementById('course-types');
    if (!container) return;
    
    container.innerHTML = '';
    
    courseTypes.forEach(type => {
        const courseTypeEl = document.createElement('div');
        courseTypeEl.className = 'course-type';
        courseTypeEl.dataset.type = type.id;
        
        courseTypeEl.innerHTML = `
            <div class="course-type-icon">${getIconForCourseType(type.id)}</div>
            <h3>${type.name}</h3>
        `;
        
        container.appendChild(courseTypeEl);
    });
}

// Get icon for course type
function getIconForCourseType(type) {
    const icons = {
        'degree': '🎓',
        'diploma': '📜',
        'kmtc': '🏥',
        'certificate': '📄',
        'artisan': '🔧'
    };
    
    return icons[type] || '📚';
}

// Set up event listeners
function setupEventListeners() {
    // Course type selection
    document.addEventListener('click', function(e) {
        if (e.target.closest('.course-type')) {
            const courseTypeEl = e.target.closest('.course-type');
            const type = courseTypeEl.dataset.type;
            
            courseTypeEl.classList.toggle('selected');
            
            if (courseTypeEl.classList.contains('selected')) {
                if (!selectedCourseTypes.includes(type)) {
                    selectedCourseTypes.push(type);
                }
            } else {
                selectedCourseTypes = selectedCourseTypes.filter(t => t !== type);
            }
            
            // Show/hide additional inputs based on selection
            const additionalInputs = document.getElementById('additional-inputs');
            if (additionalInputs) {
                if (selectedCourseTypes.includes('degree')) {
                    document.querySelector('[data-tab="cluster"]').click();
                    additionalInputs.style.display = 'block';
                    initializeClusterInputs();
                } else if (selectedCourseTypes.length > 0) {
                    document.querySelector('[data-tab="mean"]').click();
                    additionalInputs.style.display = 'block';
                } else {
                    additionalInputs.style.display = 'none';
                }
            }
        }
    });
    
    // Tab switching
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('tab')) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            e.target.classList.add('active');
            document.getElementById(`${e.target.dataset.tab}-tab`).classList.add('active');
        }
    });
    
    // Check qualification button
    const checkBtn = document.getElementById('check-qualification');
    if (checkBtn) {
        checkBtn.addEventListener('click', checkQualification);
    }

    // Sidebar toggle (hamburger) behavior
    const sidebarToggle = document.getElementById('sidebarToggle');
    const siteSidebar = document.getElementById('siteSidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    if (sidebarToggle && siteSidebar) {
        sidebarToggle.addEventListener('click', function () {
            toggleSidebar();
        });
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', function () {
            closeSidebar();
        });
    }

    // Close sidebar when a link inside it is clicked (on small screens)
    if (siteSidebar) {
        siteSidebar.addEventListener('click', function (e) {
            const link = e.target.closest('a');
            if (link && window.innerWidth < 992) {
                closeSidebar();
            }
        });
    }
}

// Sidebar helper functions
function openSidebar() {
    const siteSidebar = document.getElementById('siteSidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const main = document.querySelector('.main-content');
    if (siteSidebar) {
        siteSidebar.classList.remove('collapsed');
        siteSidebar.classList.add('open');
        // Set toggle button aria-expanded and make links focusable
        const toggle = document.querySelector('.menu-toggle') || document.getElementById('sidebarToggle');
        if (toggle) toggle.setAttribute('aria-expanded', 'true');
        Array.from(siteSidebar.querySelectorAll('a')).forEach(a => a.removeAttribute('tabindex'));
    }
    if (sidebarOverlay) sidebarOverlay.classList.add('show');
    if (main) main.classList.remove('full');
}

function closeSidebar() {
    const siteSidebar = document.getElementById('siteSidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const main = document.querySelector('.main-content');
    if (siteSidebar) {
        siteSidebar.classList.add('collapsed');
        siteSidebar.classList.remove('open');
        // Set toggle button aria-expanded and remove links from tab order
        const toggle = document.querySelector('.menu-toggle') || document.getElementById('sidebarToggle');
        if (toggle) toggle.setAttribute('aria-expanded', 'false');
        Array.from(siteSidebar.querySelectorAll('a')).forEach(a => a.setAttribute('tabindex', '-1'));
    }
    if (sidebarOverlay) sidebarOverlay.classList.remove('show');
    if (main) main.classList.add('full');
}

function toggleSidebar() {
    const siteSidebar = document.getElementById('siteSidebar');
    if (!siteSidebar) return;
    if (siteSidebar.classList.contains('open')) {
        closeSidebar();
    } else {
        openSidebar();
    }
}

// Collect user inputs
function collectUserInputs() {
    // Collect grades
    userGrades = {};
    document.querySelectorAll('.subject-grade').forEach(select => {
        const subjectCode = select.id.replace('subject-', '');
        if (select.value) {
            userGrades[subjectCode] = select.value;
        }
    });
    
    // Collect cluster points if degree is selected
    clusterPoints = {};
    if (selectedCourseTypes.includes('degree')) {
        for (let i = 1; i <= 20; i++) {
            const cluster = `cluster_${i}`;
            const input = document.getElementById(`cluster-${cluster}`);
            if (input) {
                clusterPoints[cluster] = input.value ? parseFloat(input.value) : 0;
            }
        }
    }
    
    // Collect mean grade if non-degree courses are selected
    meanGrade = '';
    if (selectedCourseTypes.some(type => type !== 'degree')) {
        const meanGradeInput = document.getElementById('mean-grade');
        if (meanGradeInput) {
            meanGrade = meanGradeInput.value;
        }
    }
}

// Validate inputs
function validateInputs() {
    if (selectedCourseTypes.length === 0) {
        alert('Please select at least one course type.');
        return false;
    }
    
    if (Object.keys(userGrades).length === 0) {
        alert('Please enter at least one subject grade.');
        return false;
    }
    
    if (selectedCourseTypes.includes('degree')) {
        const hasClusterPoints = Object.values(clusterPoints).some(points => points > 0);
        if (!hasClusterPoints) {
            alert('Please enter at least one cluster point for degree courses.');
            return false;
        }
    }
    
    if (selectedCourseTypes.some(type => type !== 'degree') && !meanGrade) {
        alert('Please select your mean grade for non-degree courses.');
        return false;
    }
    
    return true;
}

// Check qualification by calling the backend API
async function checkQualification() {
    collectUserInputs();
    
    if (!validateInputs()) {
        return;
    }
    
    // Show loader
    const loader = document.getElementById('loader');
    if (loader) loader.style.display = 'block';
    
    try {
        // Prepare data for API request
        const requestData = {
            course_types: selectedCourseTypes,
            grades: userGrades,
            cluster_points: clusterPoints,
            mean_grade: meanGrade
        };
        
        // Make API call to backend
        const response = await fetch(`${API_BASE_URL}/api/check-qualification`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            // Store results in sessionStorage and redirect to results page
            sessionStorage.setItem('qualificationResults', JSON.stringify(result));
            sessionStorage.setItem('userInputs', JSON.stringify({
                grades: userGrades,
                clusterPoints: clusterPoints,
                meanGrade: meanGrade,
                courseTypes: selectedCourseTypes
            }));
            
            window.location.href = 'results.html';
        } else {
            alert('Failed to check qualifications: ' + (result.error || 'Unknown error'));
        }
        
    } catch (error) {
        console.error('Error checking qualification:', error);
        alert('Failed to check qualifications. Please make sure the backend server is running.');
    } finally {
        // Hide loader
        if (loader) loader.style.display = 'none';
    }
}

// For results.html - display the qualification results
function displayResults() {
    if (window.location.pathname.endsWith('results.html')) {
        const results = JSON.parse(sessionStorage.getItem('qualificationResults') || '{}');
        const userInputs = JSON.parse(sessionStorage.getItem('userInputs') || '{}');
        
        if (!results.qualifying_courses) {
            window.location.href = 'base.html';
            return;
        }
        
        const resultsContainer = document.getElementById('results-container');
        const resultsSummary = document.getElementById('results-summary');
        const resultsList = document.getElementById('results-list');
        
        if (results.qualifying_courses.length === 0) {
            resultsSummary.innerHTML = `
                <div class="alert alert-danger">
                    You do not qualify for any courses based on your input.
                </div>
            `;
        } else {
            resultsSummary.innerHTML = `
                <div class="alert alert-success">
                    You qualify for ${results.qualifying_courses.length} courses across ${userInputs.courseTypes.length} course type(s).
                </div>
            `;
            
            // Group courses by type
            const coursesByType = {};
            results.qualifying_courses.forEach(course => {
                if (!coursesByType[course.course_type]) {
                    coursesByType[course.course_type] = [];
                }
                coursesByType[course.course_type].push(course);
            });
            
            // Display courses by type
            for (const [type, courses] of Object.entries(coursesByType)) {
                const typeSection = document.createElement('div');
                typeSection.className = 'course-type-section';
                
                const typeName = type.charAt(0).toUpperCase() + type.slice(1);
                typeSection.innerHTML = `<h3>${typeName} Courses</h3>`;
                
                courses.forEach(course => {
                    const courseItem = document.createElement('div');
                    courseItem.className = 'course-item';
                    
                    let detailsHtml = `
                        <div class="course-name">${course.programme_name || 'N/A'}</div>
                        <div class="course-details">
                            <div>Institution: ${course.institution_name || 'N/A'}</div>
                            <div>Program Code: ${course.programme_code || 'N/A'}</div>
                    `;
                    
                    if (course.cut_off_points) {
                        detailsHtml += `<div>Cut-off Points: ${course.cut_off_points}</div>`;
                    }
                    
                    if (course.minimum_grade && course.minimum_grade.mean_grade) {
                        detailsHtml += `<div>Minimum Mean Grade: ${course.minimum_grade.mean_grade}</div>`;
                    }
                    
                    detailsHtml += `<div>Type: ${typeName}</div>`;
                    detailsHtml += `</div></div>`;
                    
                    courseItem.innerHTML = detailsHtml;
                    typeSection.appendChild(courseItem);
                });
                
                resultsList.appendChild(typeSection);
            }
        }
        
        // Display user inputs
        const userInputsSection = document.getElementById('user-inputs');
        if (userInputsSection) {
            let inputsHtml = `<h3>Your Inputs</h3>`;
            
            inputsHtml += `<h4>Grades:</h4>`;
            for (const [code, grade] of Object.entries(userInputs.grades || {})) {
                const subjectName = subjects[code] || code;
                inputsHtml += `<p>${subjectName}: ${grade}</p>`;
            }
            
            if (userInputs.clusterPoints && Object.values(userInputs.clusterPoints).some(p => p > 0)) {
                inputsHtml += `<h4>Cluster Points:</h4>`;
                for (const [cluster, points] of Object.entries(userInputs.clusterPoints || {})) {
                    if (points > 0) {
                        inputsHtml += `<p>${cluster}: ${points}</p>`;
                    }
                }
            }
            
            if (userInputs.meanGrade) {
                inputsHtml += `<h4>Mean Grade: ${userInputs.meanGrade}</h4>`;
            }
            
            userInputsSection.innerHTML = inputsHtml;
        }
        
        if (resultsContainer) resultsContainer.style.display = 'block';
    }
}

// Call displayResults when results.html loads
if (window.location.pathname.endsWith('results.html')) {
    document.addEventListener('DOMContentLoaded', displayResults);
}