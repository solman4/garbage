// static/main.js

document.addEventListener('DOMContentLoaded', () => {
    // Kết nối với Socket.IO
    const socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);

    // Xử lý sự kiện kết nối thành công
    socket.on('connect', () => {
        console.log('Connected to server with socket ID:', socket.id);
    });

    // Xử lý sự kiện ngắt kết nối
    socket.on('disconnect', () => {
        console.log('Disconnected from server');
    });

    // Xử lý sự kiện nhận khung hình video từ server
    socket.on('video_frame', (image_base64) => {
        console.log('Received video_frame');
        const img = document.getElementById('video-stream');
        if (img) {
            img.src = 'data:image/jpeg;base64,' + image_base64;
        } else {
            console.warn('Cannot find element with id "video-stream"');
        }
    });

    socket.on('violation_update', (violation) => {
        renderViolation(violation);
    });

    socket.on('violation_history', (history) => {
        history.forEach(renderViolation);
    });

    // Fetch và hiển thị vi phạm
    function renderViolation(violation) {
        const violationsList = document.getElementById('violations-list');
        const violationCard = document.createElement('div');
        violationCard.classList.add('violation-card', 'animate__animated', 'animate__bounceIn');
        console.log('Image URL:', violation.image_url);
        violationCard.innerHTML = `
            <div class="violation-image">
                <img src="${violation.image_url}" alt="Vi Phạm">
            </div>
            <div class="violation-details">
                <h4>Chi Tiết Vi Phạm</h4>
                <p><strong>Mã Nhân Viên:</strong> ${violation.person_id}</p>
                <p><strong>Tên Người Vi Phạm:</strong> <a href="#" class="person-name" data-person-id="${violation.person_id}">${violation.person_name || 'Người vi phạm ' + violation.person_id}</a></p>
                <p><strong>Mã Rác Thải:</strong> ${violation.garbage_id}</p>
                <p><strong>Thời Gian:</strong> ${new Date(violation.timestamp * 1000).toLocaleString()}</p>
                <div class="violation-actions">
                    <button class="btn-view">Xem Chi Tiết</button>
                    <button class="btn-resolve">Đánh Dấu Đã Xử Lý</button>
                </div>
            </div>
        `;

        // Thêm sự kiện nhấp vào tên người vi phạm
        const personNameLink = violationCard.querySelector('.person-name');
        personNameLink.addEventListener('click', (e) => {
            e.preventDefault();
            const personId = e.target.getAttribute('data-person-id');
            showPersonDetails(personId);
        });

        violationsList.prepend(violationCard);
    }

    // Hàm hiển thị thông tin chi tiết người vi phạm trong modal
    function showPersonDetails(personId) {
        const modal = document.getElementById('personDetailsModal');
        const detailsContainer = document.getElementById('personDetails');

        // Fetch thông tin người vi phạm từ backend
        fetch(`/api/person/${personId}`)
            .then(response => response.json())
            .then(person => {
                detailsContainer.innerHTML = `
                    <div class="person-info">
                        <img src="${person.face_image}" alt="Ảnh Nhận Dạng" class="person-face">
                        <p><strong>Họ và Tên:</strong> ${person.name}</p>
                        <p><strong>ID:</strong> ${person.id}</p>
                        <p><strong>Chức Vụ:</strong> ${person.position}</p>
                        <p><strong>Phòng Ban:</strong> ${person.department}</p>
                        <p><strong>Số Vi Phạm:</strong> ${person.violation_count}</p>
                    </div>
                `;
                modal.style.display = "block";
            })
            .catch(error => {
                console.error('Error fetching person details:', error);
                detailsContainer.innerHTML = `<p>Không thể tải thông tin chi tiết.</p>`;
                modal.style.display = "block";
            });
    }

    // Đóng modal khi nhấp vào dấu X hoặc bên ngoài modal
    const modal = document.getElementById('personDetailsModal');
    const closeBtn = modal.querySelector('.close');

    closeBtn.onclick = () => {
        modal.style.display = "none";
    }

    window.onclick = (e) => {
        if (e.target == modal) {
            modal.style.display = "none";
        }
    }
});
