// static/js/offline-storage.js
class OfflineStorage {
  constructor() {
    this.dbName = 'kuccps-offline-db';
    this.version = 1;
    this.db = null;
    this.initializeDB();
  }
async cacheCoursesForOffline(flow, courses) {
    if (!this.db) await this.initializeDB();
    
    return new Promise((resolve, reject) => {
        const transaction = this.db.transaction(['offline_courses'], 'readwrite');
        const store = transaction.objectStore('offline_courses');
        
        // Store courses for offline access
        const cacheData = {
            flow: flow,
            courses: courses.slice(0, 50), // Limit for offline
            cachedAt: new Date().toISOString()
        };
        
        store.put(cacheData);
        
        transaction.oncomplete = () => {
            console.log(`✅ Cached ${courses.length} ${flow} courses for offline`);
            resolve();
        };
        
        transaction.onerror = (event) => reject(event.target.error);
    });
}
  async initializeDB() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.version);
      
      request.onerror = (event) => {
        console.error('IndexedDB error:', event.target.error);
        reject(event.target.error);
      };
      
      request.onsuccess = (event) => {
        this.db = event.target.result;
        console.log('IndexedDB initialized');
        resolve(this.db);
      };
      
      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        
        // Create object stores
        if (!db.objectStoreNames.contains('courses')) {
          const courseStore = db.createObjectStore('courses', { keyPath: '_id' });
          courseStore.createIndex('flow', 'flow', { unique: false });
          courseStore.createIndex('collection', 'collection', { unique: false });
        }
        
        if (!db.objectStoreNames.contains('basket')) {
          const basketStore = db.createObjectStore('basket', { keyPath: 'basket_id' });
          basketStore.createIndex('added_at', 'added_at', { unique: false });
        }
        
        if (!db.objectStoreNames.contains('user_grades')) {
          db.createObjectStore('user_grades', { keyPath: 'flow' });
        }
        
        if (!db.objectStoreNames.contains('pending_actions')) {
          const pendingStore = db.createObjectStore('pending_actions', { 
            keyPath: 'id',
            autoIncrement: true 
          });
          pendingStore.createIndex('type', 'type', { unique: false });
          pendingStore.createIndex('status', 'status', { unique: false });
        }
      };
    });
  }

  // Course operations
  async saveCourses(flow, courses) {
    if (!this.db) await this.initializeDB();
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['courses'], 'readwrite');
      const store = transaction.objectStore('courses');
      
      // Clear existing courses for this flow
      const clearRequest = store.index('flow').openCursor(IDBKeyRange.only(flow));
      clearRequest.onsuccess = (event) => {
        const cursor = event.target.result;
        if (cursor) {
          store.delete(cursor.primaryKey);
          cursor.continue();
        } else {
          // Add new courses
          courses.forEach(course => {
            course.flow = flow;
            store.add(course);
          });
        }
      };
      
      transaction.oncomplete = () => {
        console.log(`Saved ${courses.length} ${flow} courses offline`);
        resolve();
      };
      
      transaction.onerror = (event) => {
        reject(event.target.error);
      };
    });
  }

  async getCourses(flow) {
    if (!this.db) await this.initializeDB();
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['courses'], 'readonly');
      const store = transaction.objectStore('courses');
      const index = store.index('flow');
      const request = index.getAll(IDBKeyRange.only(flow));
      
      request.onsuccess = (event) => {
        resolve(event.target.result || []);
      };
      
      request.onerror = (event) => {
        reject(event.target.error);
      };
    });
  }

  // Basket operations
  async saveBasketItem(item) {
    if (!this.db) await this.initializeDB();
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['basket'], 'readwrite');
      const store = transaction.objectStore('basket');
      store.put(item);
      
      transaction.oncomplete = () => resolve();
      transaction.onerror = (event) => reject(event.target.error);
    });
  }

  async getBasket() {
    if (!this.db) await this.initializeDB();
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['basket'], 'readonly');
      const store = transaction.objectStore('basket');
      const request = store.getAll();
      
      request.onsuccess = (event) => resolve(event.target.result || []);
      request.onerror = (event) => reject(event.target.error);
    });
  }

  async removeBasketItem(basketId) {
    if (!this.db) await this.initializeDB();
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['basket'], 'readwrite');
      const store = transaction.objectStore('basket');
      store.delete(basketId);
      
      transaction.oncomplete = () => resolve();
      transaction.onerror = (event) => reject(event.target.error);
    });
  }

  // User data operations
  async saveUserGrades(flow, grades, meanGrade = null) {
    if (!this.db) await this.initializeDB();
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['user_grades'], 'readwrite');
      const store = transaction.objectStore('user_grades');
      
      const data = {
        flow: flow,
        grades: grades,
        meanGrade: meanGrade,
        savedAt: new Date().toISOString()
      };
      
      store.put(data);
      
      transaction.oncomplete = () => resolve();
      transaction.onerror = (event) => reject(event.target.error);
    });
  }

  async getUserGrades(flow) {
    if (!this.db) await this.initializeDB();
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['user_grades'], 'readonly');
      const store = transaction.objectStore('user_grades');
      const request = store.get(flow);
      
      request.onsuccess = (event) => resolve(event.target.result);
      request.onerror = (event) => reject(event.target.error);
    });
  }

  // Pending actions (for sync when online)
  async addPendingAction(type, data) {
    if (!this.db) await this.initializeDB();
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['pending_actions'], 'readwrite');
      const store = transaction.objectStore('pending_actions');
      
      const action = {
        type: type,
        data: data,
        status: 'pending',
        createdAt: new Date().toISOString()
      };
      
      store.add(action);
      
      transaction.oncomplete = () => resolve();
      transaction.onerror = (event) => reject(event.target.error);
    });
  }

  async getPendingActions() {
    if (!this.db) await this.initializeDB();
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['pending_actions'], 'readonly');
      const store = transaction.objectStore('pending_actions');
      const request = store.getAll();
      
      request.onsuccess = (event) => resolve(event.target.result || []);
      request.onerror = (event) => reject(event.target.error);
    });
  }

  // Sync when back online
  async syncAll() {
    if (!navigator.onLine) return;
    
    const actions = await this.getPendingActions();
    
    for (const action of actions) {
      try {
        switch (action.type) {
          case 'basket_add':
            await this.syncBasketAdd(action.data);
            break;
          case 'basket_remove':
            await this.syncBasketRemove(action.data);
            break;
          // Add more action types as needed
        }
      } catch (error) {
        console.error('Sync failed for action:', action, error);
      }
    }
    
    console.log('Offline sync completed');
  }

  async syncBasketAdd(data) {
    // Call your API to add to basket
    const response = await fetch('/add-to-basket', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data)
    });
    
    return response.ok;
  }

  async syncBasketRemove(data) {
    // Call your API to remove from basket
    const response = await fetch('/remove-from-basket', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data)
    });
    
    return response.ok;
  }
}

// Initialize offline storage
const offlineStorage = new OfflineStorage();

// Export for use in other files
window.OfflineStorage = offlineStorage;