document.addEventListener('DOMContentLoaded', function () {
    // 초기 데이터 로드
    loadGardeners();
    loadProgressData();
    loadTodayAttendance();
    loadFullAttendance();
    checkAuthStatus();

    // 로그인 버튼 이벤트 리스너
    document.getElementById('login-btn').addEventListener('click', function() {
        window.location.href = '/api/auth/login';
    });

    // 로그아웃 버튼 이벤트 리스너
    document.getElementById('logout-btn').addEventListener('click', function() {
        window.location.href = '/api/auth/logout';
    });

    // 새로고침 버튼 이벤트 리스너
    document.getElementById('refresh-btn').addEventListener('click', function() {
        loadGardeners();
        loadProgressData();
        loadTodayAttendance();
        loadFullAttendance();
        showNotification('출석부가 갱신되었습니다.');
    });

    // 정원사들 목록 로드
    function loadGardeners() {
        fetch('/api/users')
            .then(response => response.json())
            .then(data => {
                const gardenersList = document.getElementById('gardeners-list');
                gardenersList.innerHTML = '';

                data.forEach(user => {
                    const userDiv = document.createElement('div');
                    userDiv.className = 'gardener';
                    userDiv.innerHTML = `
                <a href="/users/${user.github_id}" title="${user.github_id}님의 프로필 보기">
                    <img src="${user.github_profile_url}" alt="${user.github_id}" title="${user.github_id}">
                    <span>${user.github_id}</span>
                </a>
            `;
                    gardenersList.appendChild(userDiv);
                });
            });
    }

    // 인증 상태 확인
    function checkAuthStatus() {
        fetch('/api/auth/me')
            .then(response => {
                if (!response.ok) {
                    throw new Error('인증 실패');
                }
                return response.json();
            })
            .then(userData => {
                // 로그인 성공 상태
                document.getElementById('login-btn').classList.add('hidden');
                const userProfile = document.getElementById('user-profile');
                userProfile.classList.remove('hidden');
                
                // 사용자 정보 표시
                document.getElementById('user-avatar').src = userData.github_profile_url;
                document.getElementById('user-name').textContent = userData.github_id;
                
                // 출석부 갱신 버튼 표시 (junho85 유저만)
                const refreshBtn = document.getElementById('refresh-btn');
                if (userData.github_id === 'junho85') {
                    refreshBtn.classList.remove('hidden');
                } else {
                    refreshBtn.classList.add('hidden');
                }
            })
            .catch(error => {
                // 로그인 안된 상태
                document.getElementById('login-btn').classList.remove('hidden');
                document.getElementById('user-profile').classList.add('hidden');
                document.getElementById('refresh-btn').classList.add('hidden');
            });
    }

    // 알림 메시지 표시
    function showNotification(message, isError = false) {
        const notification = document.createElement('div');
        notification.className = isError ? 'notification error' : 'notification';
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // 3초 후 알림 제거
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
    
    // 진행률 데이터 로드
    function loadProgressData() {
        fetch('/api/attendance/stats')
            .then(response => response.json())
            .then(data => {
                // 진행률 계산
                const totalDays = data.total_days;           // 총 프로젝트 일수 (설정값)
                const daysCompleted = data.days_completed;   // 현재까지 진행된 일수
                const progressPercent = Math.round((daysCompleted / totalDays) * 100);
                
                // 진행률 표시
                document.getElementById('progress-text').textContent = 
                    `총 ${totalDays}일 중 ${daysCompleted}일 진행 (${progressPercent}%)`;
                
                // 프로그레스 바 업데이트
                document.getElementById('progress-fill').style.width = `${progressPercent}%`;
            })
            .catch(error => {
                console.error('진행률 데이터 로드 중 오류 발생:', error);
                showNotification('진행률 데이터를 불러오는 중 오류가 발생했습니다.', true);
            });
    }

    // 날짜를 "YYYY-MM-DD" 형식으로 변환해 반환하는 함수
    function getFormattedDate(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0'); // 월은 0부터 시작하므로 +1
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }
    
    // 오늘의 출석 현황 로드
    function loadTodayAttendance() {
        // 오늘 날짜 가져오기
        const today = new Date();
        const formattedDate = getFormattedDate(today)

        // 날짜 표시
        const options = { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' };
        document.getElementById('today-date').textContent = today.toLocaleDateString('ko-KR', options);
        
        // 오늘의 출석 데이터 불러오기
        fetch(`/api/attendance/${formattedDate}`)
            .then(response => response.json())
            .then(attendanceData => {
                // 사용자 정보 불러오기 (프로필 이미지 등)
                fetch('/api/users')
                    .then(response => response.json())
                    .then(usersData => {
                        const attendanceContainer = document.getElementById('today-attendance');
                        attendanceContainer.innerHTML = '';
                        
                        // 사용자별 출석 정보 맵 생성
                        const attendanceMap = {};
                        attendanceData.forEach(a => {
                            attendanceMap[a.github_id] = a.is_attended;
                        });
                        
                        // 모든 사용자에 대해 출석 현황 표시
                        usersData.forEach(user => {
                            const isAttended = attendanceMap[user.github_id] || false;
                            const attendanceEmoji = isAttended ? '🌱' : '💤';
                            const attendanceClass = isAttended ? 'attended' : 'absent';
                            
                            const userDiv = document.createElement('div');
                            userDiv.className = `gardener-attendance ${attendanceClass}`;
                            userDiv.innerHTML = `
                                <img src="${user.github_profile_url}" alt="${user.github_id}" title="${user.github_id}">
                                <div class="attendance-emoji">${attendanceEmoji}</div>
                                <span class="name">${user.github_id}</span>
                            `;
                            attendanceContainer.appendChild(userDiv);
                        });
                    });
            })
            .catch(error => {
                console.error('오늘의 출석 현황 로드 중 오류 발생:', error);
                showNotification('출석 현황 데이터를 불러오는 중 오류가 발생했습니다.', true);
            });
    }
    
    // 전체 출석부 로드
    function loadFullAttendance() {
        fetch('/api/attendance/stats')
            .then(response => response.json())
            .then(data => {
                // 전체 통계 데이터 표시
                document.getElementById('overall-attendance-rate').textContent = `${data.overall_attendance_rate}%`;
                document.getElementById('total-present').textContent = data.total_present;
                document.getElementById('total-absent').textContent = data.total_absent;
                
                // 날짜 헤더 생성
                const datesHeader = document.getElementById('dates-header');
                // 기존 기본 헤더를 제외하고 날짜 헤더만 새로 생성
                while (datesHeader.childElementCount > 3) {
                    datesHeader.removeChild(datesHeader.lastChild);
                }
                
                // 날짜별 헤더 추가
                data.dates.forEach(dateStr => {
                    const date = new Date(dateStr);
                    const th = document.createElement('th');
                    th.className = 'date-cell';
                    
                    // 날짜 형식: MM/DD (MON) - 반응형으로 표시
                    const month = date.getMonth() + 1;
                    const day = date.getDate();
                    const dayOfWeek = ['일', '월', '화', '수', '목', '금', '토'][date.getDay()];
                    
                    th.innerHTML = `
                        <div class="date-header">
                            <span class="date-full">${month}/${day} (${dayOfWeek})</span>
                            <span class="date-short">${month}/${day}</span>
                        </div>
                    `;
                    datesHeader.appendChild(th);
                });
                
                // 사용자별 출석 데이터 생성
                const attendanceBody = document.getElementById('attendance-data');
                attendanceBody.innerHTML = '';
                
                data.users.forEach(user => {
                    const tr = document.createElement('tr');
                    
                    // 순위 셀
                    const rankTd = document.createElement('td');
                    rankTd.className = 'fixed-column';
                    rankTd.innerHTML = `<span class="user-rank">${user.rank}</span>`;
                    tr.appendChild(rankTd);
                    
                    // 사용자 정보 셀
                    const userTd = document.createElement('td');
                    userTd.className = 'fixed-column';
                    userTd.innerHTML = `
                        <div class="user-cell">
                            <img src="https://github.com/${user.github_id}.png" alt="${user.github_id}">
                            <span>${user.github_id}</span>
                        </div>
                    `;
                    tr.appendChild(userTd);
                    
                    // 출석률 셀
                    const rateTd = document.createElement('td');
                    rateTd.className = 'fixed-column';
                    rateTd.innerHTML = `<span class="attendance-rate">${user.attendance_rate}%</span>`;
                    tr.appendChild(rateTd);
                    
                    // 날짜별 출석 현황 셀
                    user.attendance.forEach(isAttended => {
                        const td = document.createElement('td');
                        td.className = 'date-cell';
                        const emoji = isAttended ? '🌱' : '❌';
                        const colorClass = isAttended ? 'attended' : 'absent';
                        td.innerHTML = `<span class="attendance-mark ${colorClass}">${emoji}</span>`;
                        tr.appendChild(td);
                    });
                    
                    attendanceBody.appendChild(tr);
                });
                
                // 일별 출석률 행 생성
                const dailyRatesRow = document.getElementById('daily-rates');
                // 기존 기본 셀을 제외하고 날짜별 셀만 새로 생성
                while (dailyRatesRow.childElementCount > 1) {
                    dailyRatesRow.removeChild(dailyRatesRow.lastChild);
                }
                
                // 일별 출석률 셀 추가
                data.daily_rates.forEach(dateRate => {
                    const td = document.createElement('td');
                    td.className = 'date-cell';
                    td.textContent = `${dateRate.rate}%`;
                    dailyRatesRow.appendChild(td);
                });
            })
            .catch(error => {
                console.error('전체 출석부 데이터 로드 중 오류 발생:', error);
                showNotification('출석부 데이터를 불러오는 중 오류가 발생했습니다.', true);
            });
    }
});