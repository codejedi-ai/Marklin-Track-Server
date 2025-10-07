

struct heap {
	// an array containing the heap, pointers to the data in the datastructure heapMember
	void** heapData;
	int size, capacity;
	// make a function pointer for the comparison function
	int (*compare)(void*, void*);
	// it would return:
	//  1 if the first argument is more fabourable than the second, 
	//  0 if they are equal, 
	// -1 if the first argument is less fabourable than the second
};
char isEmpty(struct heap* h);
void initHeap(struct heap* h, int (*compare)(void*, void*));
// make the heap insert function
void insert(struct heap* h, void* data);

void* removeMax(struct heap* h);