using UnityEngine;

/// <summary>
/// Simple FPS-style controller for moving a capsule and looking around.
/// Requires a CharacterController component on the same GameObject.
/// </summary>
[RequireComponent(typeof(CharacterController))]
public class SimplePlayerController : MonoBehaviour
{
    // 🔹 Networking
    private MasterServerClient networkClient;

    [Header("Network Settings")]
    [Tooltip("How many times per second to send position updates to the server.")]
    public float networkUpdateRate = 10f; // 10 updates per second
    private float networkUpdateTimer = 0f;
    private Vector3 lastSentPosition;
    private float minDistanceToSend = 0.01f; // Only send if moved this far

    [Header("Movement Settings")]
    [Tooltip("Speed at which the player moves forward and sideways.")]
    public float movementSpeed = 5.0f;

    [Tooltip("Gravity acceleration (set high for quick testing).")]
    public float gravity = 20.0f;

    [Header("Look Settings")]
    [Tooltip("Sensitivity of the mouse for looking left/right and up/down.")]
    public float mouseSensitivity = 2.0f;

    [Tooltip("Maximum angle the camera can look up or down.")]
    public float lookXLimit = 45.0f;

    [Header("Third Person Camera Settings")]
    [Tooltip("Distance of the camera behind the player.")]
    public float cameraDistance = 5.0f;

    [Tooltip("Height of the camera above the player.")]
    public float cameraHeight = 2.0f;

    [Tooltip("How smoothly the camera follows the player.")]
    public float cameraSmoothing = 5.0f;

    [Header("Collision Settings")]
    [Tooltip("Maximum height the player can step over (like stairs).")]
    public float stepHeight = 0.3f;

    [Tooltip("Maximum slope angle the player can climb.")]
    public float slopeLimit = 45.0f;

    [Tooltip("Collision skin width to prevent getting stuck.")]
    public float skinWidth = 0.08f;

    // Private variables for character logic
    private CharacterController characterController;
    private Vector3 moveDirection = Vector3.zero;
    private float rotationX = 0;
    private float rotationY = 0;

    // Reference to the camera for third person view
    private Camera playerCamera;
    private Vector3 cameraVelocity = Vector3.zero;

    void Start()
    {
        // 1. Get the CharacterController component
        characterController = GetComponent<CharacterController>();
        networkClient = FindObjectOfType<MasterServerClient>();

        // IMPORTANT DEBUG CHECKS:
        if (characterController == null)
        {
            Debug.LogError("CharacterController not found! Movement will not work. Please ensure the Player object has a CharacterController component.");
        }
        else
        {
            // Configure CharacterController for proper collision handling
            characterController.stepOffset = stepHeight;      // Can step over obstacles up to stepHeight units high
            characterController.slopeLimit = slopeLimit;      // Can climb slopes up to slopeLimit degrees
            characterController.skinWidth = skinWidth;        // Prevents getting stuck on edges
        }

        if (networkClient == null)
        {
            Debug.LogWarning("MasterServerClient not found! Network functionality will not work.");
        }

        if (movementSpeed <= 0)
        {
            Debug.LogWarning("Movement Speed is set to zero or less! Check the Inspector and set a positive value.");
        }

        // 2. Find or create the camera for third person view
        playerCamera = GetComponentInChildren<Camera>();
        if (playerCamera == null)
        {
            // Create a new camera if none exists
            GameObject cameraObject = new GameObject("ThirdPersonCamera");
            cameraObject.transform.SetParent(null); // Don't parent to player for third person
            playerCamera = cameraObject.AddComponent<Camera>();
            Debug.Log("Created new camera for third person view.");
        }
        else
        {
            // Unparent existing camera for third person control
            playerCamera.transform.SetParent(null);
        }

        // 3. Set up initial camera position
        UpdateCameraPosition();

        // 4. Lock cursor to hide it and keep it centered for looking around
        Cursor.lockState = CursorLockMode.Locked;
        Cursor.visible = false;

        // 5. Initialize last sent position
        lastSentPosition = transform.position;
    }

    void Update()
    {
        // --- 1. HANDLE MOUSE LOOK (for camera orbit) ---
        HandleMouseLook();

        // --- 2. HANDLE MOVEMENT (WASD) ---
        HandleMovement();

        // --- 3. HANDLE GRAVITY ---
        HandleGravity();

        // --- 4. UPDATE CAMERA POSITION ---
        UpdateCameraPosition();

        // --- 5. SEND NETWORK UPDATES (at controlled rate) ---
        HandleNetworkUpdates();
    }

    void HandleNetworkUpdates()
    {
        if (networkClient == null || !networkClient.PlayerIdConfirmed)
        {
            return;
        }

        // Update timer
        networkUpdateTimer += Time.deltaTime;

        // Check if it's time to send an update
        float updateInterval = 1f / networkUpdateRate;
        if (networkUpdateTimer >= updateInterval)
        {
            Vector3 currentPos = transform.position;

            // Only send if we've moved significantly
            float distanceMoved = Vector3.Distance(currentPos, lastSentPosition);
            if (distanceMoved >= minDistanceToSend)
            {
                SendPositionUpdate(currentPos);
                lastSentPosition = currentPos;
            }

            networkUpdateTimer = 0f;
        }
    }

    void SendPositionUpdate(Vector3 pos)
    {
        var moveData = new MoveData
        {
            id = networkClient.PlayerId,
            x = pos.x,
            y = pos.y,
            z = pos.z
        };
        string movePacket = PacketFactory.Build(Protocol.PLAYER_MOVE, moveData);
        _ = networkClient.SendPacket(movePacket);

        Debug.Log($"[PLAYER] Sent position update: ({pos.x:F2}, {pos.y:F2}, {pos.z:F2})");
    }

    void HandleMouseLook()
    {
        if (playerCamera != null)
        {
            // Only rotate when middle mouse is held
            if (Input.GetMouseButton(2)) // 2 = middle mouse
            {
                Cursor.lockState = CursorLockMode.Locked;
                Cursor.visible = false;

                // Horizontal rotation (orbit around player)
                rotationY += Input.GetAxis("Mouse X") * mouseSensitivity;

                // Vertical rotation (camera up/down)
                rotationX -= Input.GetAxis("Mouse Y") * mouseSensitivity;
                rotationX = Mathf.Clamp(rotationX, -lookXLimit, lookXLimit);
            }
            else
            {
                // Unlock cursor for UI/chat interaction
                Cursor.lockState = CursorLockMode.None;
                Cursor.visible = true;
            }
        }
    }

    void HandleMovement()
    {
        if (characterController != null && characterController.isGrounded)
        {
            // Get camera-relative movement directions
            Vector3 cameraForward = Vector3.forward;
            Vector3 cameraRight = Vector3.right;

            if (playerCamera != null)
            {
                cameraForward = playerCamera.transform.forward;
                cameraRight = playerCamera.transform.right;

                // Remove vertical component for ground movement
                cameraForward.y = 0;
                cameraRight.y = 0;
                cameraForward.Normalize();
                cameraRight.Normalize();
            }

            float curSpeedX = Input.GetAxis("Vertical") * movementSpeed;
            float curSpeedY = Input.GetAxis("Horizontal") * movementSpeed;

            // Calculate movement relative to camera direction
            moveDirection = (cameraForward * curSpeedX) + (cameraRight * curSpeedY);

            // Normalize diagonal movement to prevent faster movement
            if (moveDirection.magnitude > movementSpeed)
            {
                moveDirection = moveDirection.normalized * movementSpeed;
            }

            // Rotate player to face movement direction
            if (moveDirection.magnitude > 0.1f)
            {
                Vector3 lookDirection = new Vector3(moveDirection.x, 0, moveDirection.z);
                transform.rotation = Quaternion.LookRotation(lookDirection);
            }
        }
    }

    void HandleGravity()
    {
        if (characterController != null)
        {
            // Apply gravity
            moveDirection.y -= gravity * Time.deltaTime;

            // Store the movement result to detect collisions
            CollisionFlags collisionFlags = characterController.Move(moveDirection * Time.deltaTime);

            // Reset Y velocity if we hit something above or below
            if ((collisionFlags & CollisionFlags.Above) != 0 || (collisionFlags & CollisionFlags.Below) != 0)
            {
                moveDirection.y = 0;
            }
        }
    }

    void UpdateCameraPosition()
    {
        if (playerCamera != null)
        {
            // Calculate desired camera position
            Vector3 desiredPosition = transform.position;
            desiredPosition += Quaternion.Euler(rotationX, rotationY, 0) * new Vector3(0, cameraHeight, -cameraDistance);

            // Smoothly move camera to desired position
            playerCamera.transform.position = Vector3.SmoothDamp(
                playerCamera.transform.position,
                desiredPosition,
                ref cameraVelocity,
                1f / cameraSmoothing
            );

            // Make camera look at player
            Vector3 lookTarget = transform.position + Vector3.up * (cameraHeight * 0.5f);
            playerCamera.transform.LookAt(lookTarget);
        }
    }

    // Called when the CharacterController hits a collider while performing a Move
    void OnControllerColliderHit(ControllerColliderHit hit)
    {
        // Push rigidbodies when walking into them
        Rigidbody body = hit.collider.attachedRigidbody;

        if (body != null && !body.isKinematic)
        {
            // Calculate push direction from move direction
            Vector3 pushDir = new Vector3(hit.moveDirection.x, 0, hit.moveDirection.z);

            // Apply force to the rigidbody
            body.velocity = pushDir * movementSpeed;
        }
    }
}