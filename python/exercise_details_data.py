"""Detailed exercise metadata: muscles, mistakes, tips and progressions (pure data).

One entry per built-in exercise. The data is synced into the `exercise_details`
table on startup so the library, the workout builder and the profile all read
the same information.

_d(id, muscles, mistakes, tips, easier=(), harder=(), prereq=(), related=())
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExerciseDetail:
    id: str
    muscles: tuple = ()
    mistakes: tuple = ()
    tips: tuple = ()
    easier: tuple = ()
    harder: tuple = ()
    prereq: tuple = ()
    related: tuple = ()
    equipment: str = ""


DETAILS = {}


def _d(id, muscles, mistakes, tips, easier=(), harder=(), prereq=(), related=(), equipment=""):
    DETAILS[id] = ExerciseDetail(id, tuple(muscles), tuple(mistakes), tuple(tips),
                                 tuple(easier), tuple(harder), tuple(prereq), tuple(related), equipment)


# ================================================================== PULL
_d("australian_row",
   ("Upper back", "Lats", "Biceps", "Core"),
   ("Hips sagging toward the floor", "Pulling with the arms instead of the back",
    "Hands too far forward, turning it into a shoulder press"),
   ("Set the grip just above hip height and pull the chest to the bar",
    "Keep the body in one rigid line from heel to head",
    "Think about bending the elbows behind you, not pulling with the hands"),
   easier=("wall_pushup", "scap_pull"), harder=("pullup", "chinup"),
   prereq=(), related=("assisted_pullup", "scap_pull"))

_d("assisted_pullup",
   ("Lats", "Biceps", "Forearms"),
   ("Kipping the body to get the chin up", "Pulling with the arms only",
    "Swinging the legs so the load disappears"),
   ("Start every rep from a still full hang",
    "Use the least assistance that lets you finish with a controlled negative",
    "Keep the grip on the bar and the shoulders engaged"),
   easier=("scap_pull", "australian_row"), harder=("pullup", "chinup", "negative_pullup"),
   prereq=("australian_row",), related=("pullup", "negative_pullup"))

_d("negative_pullup",
   ("Lats", "Biceps", "Forearms"),
   ("Dropping into the hang instead of lowering slowly", "Going too deep into a swing",
    "Starting the rep from a bent knee"),
   ("Lower for 4-5 seconds every rep",
    "Step up, grip, then lower to a full dead hang",
    "Pause at the bottom before the next rep"),
   easier=("scap_pull", "australian_row"), harder=("pullup", "chinup"),
   prereq=("assisted_pullup",), related=("pullup", "assisted_pullup"))

_d("scap_pull",
   ("Upper back", "Lats", "Forearms"),
   ("Bending the elbows into a full pull-up", "Shrugging the shoulders up to the ears",
    "Swinging the body"),
   ("Keep the arms completely straight and move only the shoulder blades",
    "Finish with the shoulders down and the chest slightly open",
    "Pause for one second at the top"),
   easier=("dead_hang",), harder=("pullup", "chinup"),
   prereq=(), related=("active_hang", "pullup"))

_d("chinup",
   ("Biceps", "Lats", "Forearms", "Upper back"),
   ("Swinging the hips to reach the bar", "Pulling behind the neck",
    "Letting the shoulders roll forward at the bottom"),
   ("Pull with the elbows straight down towards the ribs",
    "Keep the chest tall and the ribs down",
    "Lower all the way to a full hang between reps"),
   easier=("assisted_pullup", "australian_row"), harder=("pullup", "c2b_pullup", "l_sit_pullup"),
   prereq=("australian_row",), related=("pullup", "close_pullup"))

_d("pullup",
   ("Lats", "Biceps", "Forearms", "Upper back"),
   ("Kipping or swinging the legs", "Pulling to the neck instead of the chin",
    "Partial range of motion", "Shrugging at the top"),
   ("Start from a dead hang with the arms fully straight",
    "Pull the elbows down and back, chest to the bar",
    "Lower under control to a full hang on every rep"),
   easier=("assisted_pullup", "negative_pullup", "australian_row"),
   harder=("c2b_pullup", "l_sit_pullup", "wide_pullup", "archer_pullup"),
   prereq=("scap_pull", "australian_row"), related=("chinup", "c2b_pullup"))

_d("wide_pullup",
   ("Lats", "Biceps", "Upper back"),
   ("Pulling with the arms only", "Leaning too far back",
    "Hands drifting to a shoulder-width grip"),
   ("Lead with the elbows and pull the chest towards the bar",
    "Keep the torso upright and the legs together",
    "Use a slightly wider grip than shoulder width"),
   easier=("pullup",), harder=("c2b_pullup", "archer_pullup"),
   prereq=("pullup",), related=("pullup", "c2b_pullup"))

_d("close_pullup",
   ("Biceps", "Lats", "Forearms"),
   ("Shoulders rolling forward at the bottom", "Using a mixed grip that twists the wrists",
    "Rushing the reps"),
   ("Keep the hands about a hand-width apart",
    "Squeeze the shoulder blades together as you pull",
    "Control the descent to a full hang"),
   easier=("pullup",), harder=("chinup", "l_sit_pullup"),
   prereq=("pullup",), related=("chinup", "pullup"))

_d("c2b_pullup",
   ("Lats", "Biceps", "Upper back", "Forearms"),
   ("Kipping to reach the chest", "Pulling behind the neck",
    "Cutting the range short"),
   ("Pull high and lean back slightly so the sternum meets the bar",
    "Keep the legs still and the core braced",
    "Use a false grip if the wrists give out first"),
   easier=("pullup", "chinup"), harder=("archer_pullup", "bar_muscle_up"),
   prereq=("pullup",), related=("pullup", "bar_muscle_up"))

_d("archer_pullup",
   ("Lats", "Biceps", "Upper back"),
   ("Pulling with both arms", "Twisting the hips",
    "Not straightening the free arm"),
   ("Pull towards one hand while the other arm stays long",
    "Lower slowly and switch sides every rep",
    "Keep the shoulders level throughout"),
   easier=("pullup", "wide_pullup"), harder=("one_arm_pullup",),
   prereq=("wide_pullup", "pullup"), related=("pullup", "one_arm_pullup"))

_d("l_sit_pullup",
   ("Lats", "Core", "Hip flexors", "Biceps"),
   ("Legs dropping during the pull", "Arching the lower back",
    "Pulling with a swing"),
   ("Keep the legs locked out and parallel to the floor for the whole rep",
    "Press down hard through the hands",
    "Start with a tuck L-sit and extend the legs gradually"),
   easier=("pullup", "tuck_l_sit"), harder=("bar_muscle_up",),
   prereq=("pullup", "tuck_l_sit"), related=("l_sit", "pullup"))

_d("dead_hang",
   ("Forearms", "Lats", "Shoulders"),
   ("Letting the shoulders shrug up", "Swinging the legs",
    "Gripping so hard the forearms cramp"),
   ("Hang with a slight bend in the knees to reduce the load",
    "Keep the shoulders active rather than hanging passively",
    "Breathe calmly and switch grip if the hands burn"),
   easier=(), harder=("active_hang", "false_grip_hang", "scap_pull"),
   prereq=(), related=("active_hang", "scap_pull"))

_d("active_hang",
   ("Lats", "Upper back", "Forearms"),
   ("Shoulders still shrugging", "Swinging the body",
    "Holding the breath"),
   ("Pull the shoulder blades down towards the back pockets",
    "Keep the arms straight and the body still",
    "Think about hanging taller, not heavier"),
   easier=("dead_hang",), harder=("false_grip_hang", "pullup"),
   prereq=("dead_hang",), related=("scap_pull", "dead_hang"))

_d("false_grip_hang",
   ("Forearms", "Wrists", "Lats"),
   ("Wrists rolled forward instead of over the bar", "Swinging the legs",
    "Gripping with the fingertips only"),
   ("Wrap the wrist over the bar so the heel of the hand presses down",
    "Squeeze the glutes and keep the body in a straight line",
    "Build up slowly, the wrist tendon adapts slowly"),
   easier=("active_hang", "dead_hang"), harder=("ring_muscle_up", "mu_transition"),
   prereq=("active_hang",), related=("ring_muscle_up", "mu_transition"))

_d("one_arm_pullup",
   ("Lats", "Biceps", "Forearms", "Core"),
   ("Twisting the hips to help pull", "Using a kick-up on every rep",
    "Rushing the transition"),
   ("Train the one-arm position long before you attempt a full rep",
    "Rotate the shoulder over the bar and lower under control",
    "Practise with bands or a spotter until the pattern is automatic"),
   easier=("archer_pullup",), harder=(),
   prereq=("archer_pullup",), related=("archer_pullup", "bar_muscle_up"))

# ================================================================== PUSH
_d("wall_pushup",
   ("Chest", "Triceps", "Front delts"),
   ("Hips sagging towards the wall", "Flaring the elbows straight out",
    "Hands too low, pushing the shoulders into a shrug"),
   ("Place the hands at chest height and keep one straight line from head to heels",
    "Lower the chest to the wall, elbows at about 45 degrees",
    "Push the wall away and finish with the shoulders away from the ears"),
   easier=(), harder=("incline_pushup", "knee_pushup", "pushup"),
   prereq=(), related=("incline_pushup", "pushup"))

_d("incline_pushup",
   ("Chest", "Triceps", "Front delts", "Core"),
   ("Hips piking up", "Hands too wide",
    "Lowering to the belly instead of the chest"),
   ("Use a bench or table high enough to keep the body in a straight line",
    "Lower until the sternum touches the edge",
    "Keep the elbows at roughly 45 degrees from the torso"),
   easier=("wall_pushup", "knee_pushup"), harder=("pushup", "decline_pushup"),
   prereq=("wall_pushup",), related=("pushup", "knee_pushup"))

_d("knee_pushup",
   ("Chest", "Triceps", "Front delts", "Core"),
   ("Hips sagging", "Flaring the elbows to 90 degrees",
    "Pressing up with the lower back arched"),
   ("Set the knees under the hips and the shoulders over the hands",
    "Lower the chest between the hands, not in front of them",
    "Squeeze the glutes so the body stays rigid"),
   easier=("wall_pushup", "incline_pushup"), harder=("pushup",),
   prereq=("wall_pushup",), related=("pushup", "incline_pushup"))

_d("pushup",
   ("Chest", "Triceps", "Front delts", "Core"),
   ("Sagging the hips", "Flaring the elbows to the sides",
    "Partial range of motion", "Head looking forward instead of down"),
   ("One straight line from head to heels",
    "Hands under the shoulders, lower the chest between the hands",
    "Squeeze the glutes and brace the abs the whole time"),
   easier=("incline_pushup", "knee_pushup", "wall_pushup"),
   harder=("diamond_pushup", "decline_pushup", "wide_pushup", "pike_pushup", "pseudo_planche_pushup"),
   prereq=("incline_pushup",), related=("diamond_pushup", "decline_pushup"))

_d("wide_pushup",
   ("Chest", "Triceps", "Front delts"),
   ("Elbows flaring even wider", "Hips sagging",
    "Using a very short range"),
   ("Hands noticeably wider than the shoulders",
    "Lower until the chest is just off the floor",
    "Keep the body in one rigid line"),
   easier=("pushup",), harder=("pseudo_planche_pushup",),
   prereq=("pushup",), related=("pushup",))

_d("diamond_pushup",
   ("Triceps", "Chest", "Front delts"),
   ("Elbows shooting out to the sides", "Hips rising",
    "Hands drifting apart"),
   ("Hands together under the chest forming a diamond",
    "Keep the elbows hugging the ribs",
    "Lower the chest towards the hands, not the chin"),
   easier=("pushup",), harder=("one_arm_pushup", "pseudo_planche_pushup"),
   prereq=("pushup",), related=("pushup", "one_arm_pushup"))

_d("decline_pushup",
   ("Chest", "Triceps", "Front delts", "Core"),
   ("Hips sagging towards the floor", "Neck craning",
    "Feet not secured"),
   ("Put the feet on a bench at about hip height",
    "Keep the hips level with the shoulders",
    "Lower the chest between the hands and press away hard"),
   easier=("pushup",), harder=("pseudo_planche_pushup", "one_arm_pushup"),
   prereq=("pushup",), related=("pushup", "pike_pushup"))

_d("pike_pushup",
   ("Shoulders", "Triceps", "Chest"),
   ("Bending the knees instead of the hips", "Head touching the floor between the feet",
    "Lowering to the forehead instead of the floor"),
   ("Lift the hips high and walk the feet in until the body is steep",
    "Lower the crown of the head towards the floor between the hands",
    "Keep the legs straight and the elbows slightly forward"),
   easier=("pushup", "incline_pushup"), harder=("wall_hspu",),
   prereq=("pushup",), related=("wall_hspu", "pushup"))

_d("bench_dip",
   ("Triceps", "Front delts", "Chest"),
   ("Dropping too deep and stressing the shoulders", "Pushing the hips away from the bench",
    "Elbows flaring forward"),
   ("Hands close to the hips and shoulders down and back",
    "Lower only until the elbows reach 90 degrees",
    "Keep the back close to the bench and the feet light on the floor"),
   easier=(), harder=("dip", "korean_dip"),
   prereq=(), related=("dip", "korean_dip"))

_d("dip",
   ("Chest", "Triceps", "Front delts"),
   ("Dropping below 90 degrees and pinching the shoulders", "Leaning too far forward",
    "Shoulders shrugged at the top"),
   ("Lower until the upper arms are parallel to the ground at most",
    "Keep the torso upright, slightly forward",
    "Press down and lock out with the shoulders actively down"),
   easier=("bench_dip", "scapular_dip"), harder=("korean_dip", "ring_dip"),
   prereq=("bench_dip",), related=("bench_dip", "scapular_dip"))

_d("scapular_dip",
   ("Upper back", "Triceps", "Shoulders"),
   ("Bending the elbows into a full dip", "Shrugging the shoulders",
    "Moving the body instead of the blades"),
   ("Lock the elbows straight and move only the shoulder blades",
    "Let the shoulder blades spread and retract",
    "Pause briefly in the spread position"),
   easier=("bench_dip",), harder=("dip",),
   prereq=(), related=("dip", "support_hold"))

_d("korean_dip",
   ("Triceps", "Chest", "Front delts"),
   ("Lowering too far", "Shoulders rolled forward at the top",
    "Swinging the legs"),
   ("Body in front of the hands, chest tall and open",
    "Lower only as far as the shoulder joint stays comfortable",
    "Go gently on the shoulders and build up slowly"),
   easier=("bench_dip", "dip"), harder=(),
   prereq=("dip",), related=("bench_dip", "dip"))

_d("ring_dip",
   ("Chest", "Triceps", "Shoulders"),
   ("Rings swinging apart", "Shoulders rolled forward",
    "Turning the elbows out of the strength position"),
   ("Turn the elbows out and keep the rings close and quiet",
    "Lower between the hands, not behind them",
    "Press down so the rings stay under the shoulders"),
   easier=("dip", "bench_dip"), harder=(),
   prereq=("dip",), related=("dip", "ring_muscle_up"))

_d("archer_pushup",
   ("Chest", "Triceps", "Front delts"),
   ("Both arms bending", "Hips twisting",
    "Rushing the reps"),
   ("Lower towards one hand while the other arm stays long",
    "Keep the hips square and the body level",
    "Alternate sides and control the descent"),
   easier=("pushup", "wide_pushup"), harder=("one_arm_pushup",),
   prereq=("wide_pushup", "pushup"), related=("one_arm_pushup", "pushup"))

_d("pseudo_planche_pushup",
   ("Shoulders", "Chest", "Triceps"),
   ("Hips too high", "Elbows flaring",
    "Feet touching the ground during the lean"),
   ("Hands by the hips with the fingers turned out",
    "Shift the shoulders forward past the hands as you press",
    "Start with short leans and build the lean over time"),
   easier=("pushup", "decline_pushup"), harder=("tuck_planche",),
   prereq=("pushup",), related=("tuck_planche", "planche_lean"))

_d("one_arm_pushup",
   ("Chest", "Triceps", "Core"),
   ("Hips twisting towards the working arm", "Shoulder shrugging",
    "Partial range of motion"),
   ("Wide stance to keep the hips square",
    "Press from one hand with the body perfectly still",
    "Build up with assisted or elevated variations first"),
   easier=("archer_pushup", "diamond_pushup"), harder=(),
   prereq=("archer_pushup", "diamond_pushup"), related=("archer_pushup",))

_d("wall_hspu",
   ("Shoulders", "Triceps", "Chest"),
   ("Head hitting the floor hard", "Hips piking and bouncing",
    "Arching the lower back at the top"),
   ("Walk the feet up the wall until the body is vertical",
    "Lower the head to the floor under control, elbows bent",
    "Use a mat and build the range gradually"),
   easier=("pike_pushup",), harder=("free_hspu",),
   prereq=("pike_pushup",), related=("free_hspu", "pike_pushup"))

_d("free_hspu",
   ("Shoulders", "Triceps", "Core"),
   ("Bouncing off the wall", "Arching the back",
    "Losing the hand balance"),
   ("Balance first, then add the press",
    "Lower with the elbows tracking forward",
    "Land in a controlled handstand, not a flop"),
   easier=("wall_hspu",), harder=(),
   prereq=("wall_hspu",), related=("wall_hspu", "free_handstand"))

# ================================================================== CORE
_d("plank",
   ("Core", "Front delts", "Glutes"),
   ("Hips sagging", "Hips piking up",
    "Head looking forward instead of down", "Holding the breath"),
   ("Forearms under the shoulders, body in one straight line",
    "Tuck the pelvis slightly and squeeze the glutes",
    "Pull the elbows towards the toes and breathe steadily"),
   easier=("wall_pushup", "knee_pushup"), harder=("side_plank", "hollow_hold", "dragon_flag"),
   prereq=(), related=("hollow_hold", "side_plank"))

_d("side_plank",
   ("Obliques", "Core", "Shoulders", "Glutes"),
   ("Hips dropping to the floor", "Body bent in an L shape",
    "Shoulder collapsed towards the floor"),
   ("Stack the feet and lift the hips until the body is a straight line",
    "Push the bottom shoulder away from the ear",
    "Keep the top hip stacked over the bottom one"),
   easier=("plank",), harder=("human_flag",),
   prereq=("plank",), related=("plank", "clutch_flag"))

_d("dead_bug",
   ("Core", "Hip flexors", "Obliques"),
   ("Lower back arching off the floor", "Moving too fast",
    "Both legs dropping at the same time"),
   ("Keep the lower back pressed into the floor the whole time",
    "Extend opposite arm and leg slowly",
    "Exhale fully as the limbs reach away"),
   easier=(), harder=("hollow_hold", "hanging_leg_raise"),
   prereq=(), related=("hollow_hold", "lying_leg_raise"))

_d("hollow_hold",
   ("Core", "Hip flexors", "Shoulders"),
   ("Lower back lifting off the floor", "Legs bending to make it easier",
    "Breathing shallowly"),
   ("Press the lower back into the floor and lift the shoulders and legs",
    "Keep the legs straight and the arms reaching long",
    "Breathe into the belly, not the chest"),
   easier=("plank", "dead_bug"), harder=("l_sit", "toes_to_bar"),
   prereq=("plank",), related=("l_sit", "plank"))

_d("lying_leg_raise",
   ("Core", "Hip flexors", "Lower back"),
   ("Lower back arching as the legs lower", "Bending the knees",
    "Using momentum"),
   ("Press the lower back down and lift the legs with the abs",
    "Lower them slowly all the way without the back lifting",
    "Bend the knees to make the range easier"),
   easier=("dead_bug",), harder=("hanging_knee_raise", "hanging_leg_raise", "toes_to_bar"),
   prereq=(), related=("hanging_leg_raise", "hollow_hold"))

_d("hanging_knee_raise",
   ("Core", "Hip flexors", "Forearms"),
   ("Swinging the body", "Hips not tilting at the top",
    "Pulling on the bar to cheat"),
   ("Curl the knees up towards the chest and tilt the pelvis",
    "Control the descent, do not let the swing start",
    "Keep the grip and the shoulders locked"),
   easier=("lying_leg_raise",), harder=("hanging_leg_raise", "toes_to_bar"),
   prereq=("lying_leg_raise",), related=("hanging_leg_raise", "toes_to_bar"))

_d("hanging_leg_raise",
   ("Core", "Hip flexors", "Lats", "Forearms"),
   ("Swinging the legs", "Legs bending to cheat the height",
    "Lower back arching"),
   ("Raise straight legs to at least horizontal with control",
    "Curl the pelvis at the top to bring the legs higher",
    "Lower slowly, the negative is the harder part"),
   easier=("hanging_knee_raise",), harder=("toes_to_bar",),
   prereq=("hanging_knee_raise",), related=("toes_to_bar", "hanging_knee_raise"))

_d("ab_wheel",
   ("Core", "Front delts", "Lats"),
   ("Lower back sagging towards the floor", "Going too far",
    "Pulling with the arms instead of the abs"),
   ("Keep a rounded back and a tight core the whole way out",
    "Stop the rollout before the lower back flattens",
    "Pull back by contracting the abs, not by jerking the arms"),
   easier=("plank",), harder=("dragon_flag",),
   prereq=("plank",), related=("plank", "dragon_flag"))

_d("tuck_l_sit",
   ("Core", "Triceps", "Hip flexors"),
   ("Hips dropping behind the hands", "Rounded back",
    "Elbows locked but shoulders shrugged"),
   ("Press down through the hands and lift the hips forward",
    "Keep the back flat and the chest up",
    "Hold the knees up and the toes pointed"),
   easier=("plank",), harder=("l_sit", "l_sit_pullup"),
   prereq=("plank",), related=("l_sit", "l_sit_pullup"))

_d("l_sit",
   ("Core", "Triceps", "Hip flexors"),
   ("Hips sinking towards the floor", "Knees bending",
    "Rounded back and slumped shoulders"),
   ("Straight arms locked, legs parallel to the floor",
    "Push down hard through the hands",
    "Point the toes and keep the chest open"),
   easier=("tuck_l_sit",), harder=("l_sit_pullup", "toes_to_bar"),
   prereq=("tuck_l_sit",), related=("tuck_l_sit", "l_sit_pullup"))

_d("toes_to_bar",
   ("Core", "Hip flexors", "Lats", "Forearms"),
   ("Kipping to reach the bar", "Bending the knees",
    "Lower back arching on the descent"),
   ("Pull the legs up with the abs, not by swinging",
    "Reach the toes to the bar with straight legs",
    "Control the whole descent to a dead hang"),
   easier=("hanging_leg_raise", "hanging_knee_raise"), harder=("dragon_flag",),
   prereq=("hanging_leg_raise",), related=("hanging_leg_raise", "dragon_flag"))

_d("dragon_flag",
   ("Core", "Shoulders", "Lower back"),
   ("Lowering with the hips instead of the whole body", "Heels touching the floor early",
    "Bending at the lower back"),
   ("Hold the bench behind the head and keep the body as one rigid line",
    "Lower only as far as you can control",
    "Roll up to the start instead of sitting up"),
   easier=("ab_wheel", "hollow_hold"), harder=(),
   prereq=("hollow_hold", "ab_wheel"), related=("hollow_hold", "toes_to_bar"))

# ================================================================== LEGS
_d("squat",
   ("Quads", "Glutes", "Hamstrings", "Core"),
   ("Heels lifting off the floor", "Knees collapsing inwards",
    "Rounding the lower back", "Not going deep enough"),
   ("Feet shoulder-width, toes slightly out",
    "Sit the hips back and down, chest tall",
    "Drive through the whole foot and keep the knees tracking over the toes"),
   easier=("wall_sit", "glute_bridge"), harder=("split_squat", "bulgarian", "pistol_squat"),
   prereq=(), related=("split_squat", "glute_bridge"))

_d("lunge",
   ("Quads", "Glutes", "Hamstrings", "Core"),
   ("Knee passing the toes", "Leaning too far forward",
    "Short stride making the rear knee shoot forward"),
   ("Take a long stride so the knee stays behind the toes",
    "Lower the back knee straight down towards the floor",
    "Keep the front foot fully planted"),
   easier=("split_squat", "glute_bridge"), harder=("bulgarian", "jump_lunge"),
   prereq=(), related=("split_squat", "bulgarian"))

_d("split_squat",
   ("Quads", "Glutes", "Hamstrings", "Core"),
   ("Losing balance", "Back knee diving forward",
    "Heels lifting off the floor"),
   ("Stagger the feet so the front heel is under the back knee",
    "Lower straight down, no forward lunge",
    "Push through the front heel to stand up"),
   easier=("lunge", "glute_bridge"), harder=("bulgarian", "shrimp_squat"),
   prereq=(), related=("bulgarian", "lunge"))

_d("bulgarian",
   ("Quads", "Glutes", "Hamstrings", "Core"),
   ("Front foot too far forward", "Heels lifting",
    "Rear knee swinging forward"),
   ("Set the front foot far enough forward that the shin is vertical at the bottom",
    "Lower until the front thigh is parallel to the floor",
    "Keep the torso upright and drive through the front heel"),
   easier=("split_squat", "lunge"), harder=("shrimp_squat", "pistol_squat"),
   prereq=("split_squat",), related=("shrimp_squat", "pistol_squat"))

_d("step_up",
   ("Quads", "Glutes", "Hamstrings"),
   ("Pushing off the back foot", "Knee collapsing inwards",
    "Standing on the toes instead of the whole foot"),
   ("Place the whole foot on the box before standing up",
    "Stand tall on the box, then step down under control",
    "Keep the hips level and the knee tracking over the toes"),
   easier=("lunge",), harder=("bulgarian", "box_jump"),
   prereq=(), related=("lunge", "box_jump"))

_d("glute_bridge",
   ("Glutes", "Hamstrings", "Core"),
   ("Arching the lower back instead of driving the hips", "Pushing with the heels only",
    "Rushing the reps"),
   ("Feet flat, knees over the ankles, drive the hips up",
    "Finish with the ribs down and the glutes squeezed hard",
    "Pause for one second at the top of every rep"),
   easier=(), harder=("hollow_hold", "squat"),
   prereq=(), related=("squat", "hollow_hold"))

_d("wall_sit",
   ("Quads", "Glutes", "Core"),
   ("Hands on the thighs taking the load", "Knees drifting forward",
    "Back not flat against the wall"),
   ("Back flat, knees at 90 degrees, exactly in front of the ankles",
    "Keep the weight in the heels and the chest lifted",
    "Hold the position with steady breathing"),
   easier=(), harder=("bulgarian", "split_squat"),
   prereq=(), related=("squat", "split_squat"))

_d("calf_raise",
   ("Calves", "Core"),
   ("Bending the knees", "Cutting the range short at the top",
    "Bouncing out of the bottom"),
   ("Rise as high as the toes allow and pause at the top",
    "Lower the heels all the way down, slowly",
    "Keep the knees straight and the weight over the big toe"),
   easier=(), harder=("single_calf_raise",),
   prereq=(), related=("single_calf_raise",))

_d("single_calf_raise",
   ("Calves", "Core", "Glutes"),
   ("Leaning the torso to the side", "Using the wall to push off",
    "Knee bending"),
   ("Stand on one leg with the other foot off the floor, hold a wall only for balance",
    "Rise and lower through the full range",
    "Keep the hips square and the spine tall"),
   easier=("calf_raise",), harder=(),
   prereq=("calf_raise",), related=("calf_raise",))

_d("shrimp_squat",
   ("Quads", "Glutes", "Core"),
   ("Front heel lifting", "Knee collapsing inwards",
    "Leaning the head forward"),
   ("Hold the rear foot and touch the back knee down in front of the front foot",
    "Keep the front foot flat and the torso upright",
    "Work up from a wall-assisted version"),
   easier=("bulgarian", "split_squat"), harder=("pistol_squat",),
   prereq=("bulgarian",), related=("pistol_squat", "bulgarian"))

_d("pistol_squat",
   ("Quads", "Glutes", "Core", "Balance"),
   ("Heel lifting off the floor", "Knee collapsing inwards",
    "Leaning forward without control"),
   ("Extend the free leg forward and keep the heel down",
    "Sit straight down over the standing leg",
    "Lean the torso slightly forward and drill the balance first"),
   easier=("shrimp_squat", "bulgarian"), harder=(),
   prereq=("shrimp_squat", "split_squat"), related=("shrimp_squat", "bulgarian"))

_d("nordic_curl",
   ("Hamstrings", "Glutes", "Lower back"),
   ("Falling forward too fast", "Hips lifting instead of the heels",
    "Lowering only a few centimetres"),
   ("Anchor the feet and lower as slowly as you can",
    "Keep the hips extended and the body in one line",
    "Catch yourself with the hands and work towards a full 6-second negative"),
   easier=("glute_bridge", "lunge"), harder=(),
   prereq=(), related=("glute_bridge", "lunge"))

# ========================================================== STATIC HOLDS
_d("tuck_front_lever",
   ("Lats", "Core", "Forearms", "Shoulders"),
   ("Hips dropping below the shoulders", "Back arching",
    "Elbows bending", "Rushing the hold and failing early"),
   ("Pull the shoulders down and back before you lift",
    "Bring the knees to the chest and raise the hips to shoulder height",
    "Keep the back flat and the arms completely straight"),
   easier=("planche_lean", "active_hang"), harder=("adv_tuck_front_lever", "straddle_front_lever"),
   prereq=("active_hang", "scap_pull"), related=("adv_tuck_front_lever", "tuck_planche"))

_d("adv_tuck_front_lever",
   ("Lats", "Core", "Forearms", "Shoulders"),
   ("Hips sagging", "Back arching", "Arms bending"),
   ("Open the hips so the knees are at 90 degrees",
    "Keep the back perfectly flat, like a table",
    "Push the bar away from you to keep the shoulders active"),
   easier=("tuck_front_lever",), harder=("straddle_front_lever",),
   prereq=("tuck_front_lever",), related=("straddle_front_lever", "tuck_front_lever"))

_d("straddle_front_lever",
   ("Lats", "Core", "Forearms", "Shoulders"),
   ("Legs not straight", "Hips dropping", "Back arching"),
   ("Straighten the legs and spread them wide",
    "Keep the hips level with the shoulders",
    "Squeeze the glutes hard to lock the back"),
   easier=("adv_tuck_front_lever",), harder=("full_front_lever",),
   prereq=("adv_tuck_front_lever",), related=("full_front_lever", "tuck_planche"))

_d("full_front_lever",
   ("Lats", "Core", "Forearms", "Glutes"),
   ("Hips dipping", "Legs bending", "Wrists rolling forward"),
   ("Body completely straight and parallel to the floor",
    "Shoulders pulled down and back, wrists stacked over the hands",
    "Build towards this from the straddle lever"),
   easier=("straddle_front_lever",), harder=(),
   prereq=("straddle_front_lever",), related=("straddle_front_lever", "full_planche"))

_d("tuck_back_lever",
   ("Lats", "Core", "Shoulders", "Forearms"),
   ("Hips not level with the shoulders", "Back arching",
    "Bending at the waist instead of the hips"),
   ("Start from an inverted hang and lower the tucked body as one line",
    "Stop when the shoulders and hips are level",
    "Keep the arms straight and the shoulders active"),
   easier=("skin_the_cat",), harder=("straddle_back_lever",),
   prereq=("skin_the_cat",), related=("straddle_back_lever", "skin_the_cat"))

_d("straddle_back_lever",
   ("Lats", "Core", "Shoulders", "Forearms"),
   ("Hips too high or too low", "Legs not straight",
    "Shoulders collapsing"),
   ("Spread the straight legs and push the hips back",
    "Aim for a straight line from shoulder to toe",
    "Keep the head neutral and the shoulders pushed away from the ears"),
   easier=("tuck_back_lever",), harder=("full_back_lever",),
   prereq=("tuck_back_lever",), related=("full_back_lever", "tuck_back_lever"))

_d("full_back_lever",
   ("Lats", "Core", "Shoulders", "Forearms"),
   ("Hips sagging", "Knees bent", "Neck craning"),
   ("Legs together and completely straight",
    "Body in one horizontal line, face towards the floor",
    "Work up from the straddle lever and keep the ribs down"),
   easier=("straddle_back_lever",), harder=(),
   prereq=("straddle_back_lever",), related=("straddle_back_lever",))

_d("planche_lean",
   ("Shoulders", "Chest", "Core", "Triceps"),
   ("Hips rising", "Elbows bending", "Looking at the hands only"),
   ("Hands by the hips with the fingers turned out",
    "Shift the weight forward until the shoulders are well past the hands",
    "Keep the elbows locked and the back flat"),
   easier=("pushup",), harder=("tuck_planche",),
   prereq=("pushup",), related=("tuck_planche", "pseudo_planche_pushup"))

_d("tuck_planche",
   ("Shoulders", "Core", "Triceps", "Chest"),
   ("Hips too high", "Knees not tucked",
    "Elbows bending", "Rushing and failing early"),
   ("Lean forward over straight arms until the feet float",
    "Tuck the knees tight to the chest",
    "Push the shoulders forward past the hands and hold the shape"),
   easier=("planche_lean",), harder=("adv_tuck_planche", "straddle_planche"),
   prereq=("planche_lean",), related=("adv_tuck_planche", "planche_lean"))

_d("adv_tuck_planche",
   ("Shoulders", "Core", "Triceps", "Chest"),
   ("Hips below shoulder height", "Back arching",
    "Knees drifting away from the chest"),
   ("Hips level with the shoulders and the back flat",
    "Knees still bent but opening away from the chest",
    "Keep the elbows locked and the shoulders protracted"),
   easier=("tuck_planche",), harder=("straddle_planche",),
   prereq=("tuck_planche",), related=("straddle_planche", "tuck_planche"))

_d("straddle_planche",
   ("Shoulders", "Core", "Triceps", "Chest"),
   ("Legs together", "Hips too low", "Back arching"),
   ("Straight legs spread wide in a straddle",
    "Hips level with the shoulders, body horizontal",
    "Train the straight-arm strength with pseudo planche push-ups"),
   easier=("adv_tuck_planche",), harder=("full_planche", "dragonfly"),
   prereq=("adv_tuck_planche",), related=("full_planche", "dragonfly"))

_d("full_planche",
   ("Shoulders", "Core", "Triceps", "Chest"),
   ("Legs apart", "Hips sagging", "Wrists rolled forward"),
   ("Legs together and completely straight",
    "Body perfectly horizontal, shoulders past the hands",
    "Extensive straight-arm strength is required, build slowly"),
   easier=("straddle_planche", "dragonfly"), harder=(),
   prereq=("straddle_planche",), related=("straddle_planche", "dragonfly"))

_d("dragonfly",
   ("Shoulders", "Core", "Triceps", "Chest"),
   ("Hips too high", "Legs bending", "Wrists rolling forward"),
   ("Lean far forward with straight arms until the hips are over the hands",
    "Lift the straight legs to horizontal",
    "Work up from the straddle planche and keep the shoulders pushed up"),
   easier=("straddle_planche", "tuck_planche"), harder=("full_planche",),
   prereq=("adv_tuck_planche",), related=("straddle_planche", "full_planche"))

_d("clutch_flag",
   ("Obliques", "Core", "Shoulders", "Forearms"),
   ("Both feet touching the floor", "Hips sagging",
    "Wrists rolling around the pole"),
   ("Grip the pole with both hands and press the body away from it",
    "Lift the feet so only the hands touch the pole",
    "Keep the legs bent at first and build towards a straight body"),
   easier=("side_plank",), harder=("straddle_flag",),
   prereq=("side_plank",), related=("straddle_flag", "side_plank"))

_d("straddle_flag",
   ("Obliques", "Core", "Shoulders", "Forearms"),
   ("Body not horizontal", "Hips dropping",
    "Legs not straight"),
   ("Push out from the pole until the body is level",
    "Spread the straight legs to counter the rotation",
    "The bottom hand presses down, the top hand pulls up"),
   easier=("clutch_flag",), harder=("human_flag",),
   prereq=("clutch_flag",), related=("human_flag", "clutch_flag"))

_d("human_flag",
   ("Obliques", "Core", "Shoulders", "Forearms"),
   ("Hips sagging", "Legs not together",
    "Feet touching the ground", "Body angled instead of horizontal"),
   ("Push the lower hand down and pull the upper hand up",
    "Legs together and body perfectly horizontal",
    "Train straddle flags and side planks before this"),
   easier=("straddle_flag",), harder=(),
   prereq=("straddle_flag",), related=("straddle_flag", "clutch_flag"))

# ================================================== HANDSTAND & BALANCE
_d("wall_handstand",
   ("Shoulders", "Forearms", "Core", "Wrists"),
   ("Shoulders shrugged", "Ribs flaring",
    "Hips piking over", "Weight too close to the wall"),
   ("Chest to the wall, legs straight and together",
    "Push the floor away so the shoulders are active",
    "Squeeze the glutes and tuck the ribs to keep the hips over the shoulders"),
   easier=("crow_pose",), harder=("free_handstand",),
   prereq=("crow_pose",), related=("free_handstand", "handstand_walk"))

_d("free_handstand",
   ("Shoulders", "Core", "Forearms", "Wrists"),
   ("Kicking too hard and overshooting", "Hips piking",
    "Shoulders shrugged", "Holding the breath"),
   ("Kick up softly and steer with the fingertips and the heels of the palms",
    "Keep the hips stacked over the shoulders",
    "Practise on the wall and use a spotter while learning"),
   easier=("wall_handstand", "handstand_kickup"), harder=("press_handstand",),
   prereq=("wall_handstand",), related=("wall_handstand", "handstand_walk"))

_d("handstand_kickup",
   ("Shoulders", "Core", "Forearms"),
   ("Kicking too hard", "Coming down uncontrolled",
    "Landing on the head"),
   ("Kick up with control, find the balance point, then come down",
    "Always come down to a crouch, never to the head",
    "Practise the balance position against the wall first"),
   easier=("wall_handstand",), harder=("free_handstand",),
   prereq=("wall_handstand",), related=("free_handstand", "wall_handstand"))

_d("handstand_walk",
   ("Shoulders", "Core", "Forearms", "Wrists"),
   ("Hips swinging side to side", "Hips piking over the shoulders",
    "Steps too long", "Wrists rolling forward"),
   ("Take short steps and move the hips first, the shoulders follow",
    "Keep the body stacked over the wrists",
    "Practise on the wall before walking on the floor"),
   easier=("wall_handstand",), harder=(),
   prereq=("wall_handstand",), related=("free_handstand", "wall_handstand"))

_d("crow_pose",
   ("Shoulders", "Core", "Triceps"),
   ("Feet touching the floor", "Hips too high",
    "Wrists rolling forward", "Looking forwards instead of down"),
   ("Hands shoulder-width, fingers spread",
    "Knees rest on the upper arms and shift forward",
    "Round the upper back and look ahead to lift the feet"),
   easier=("plank", "knee_pushup"), harder=("free_handstand", "tuck_planche"),
   prereq=(), related=("free_handstand", "planche_lean"))

# =================================================== SKILL PROGRESSIONS
_d("mu_transition",
   ("Lats", "Chest", "Triceps", "Shoulders"),
   ("Pressing the bar away too early", "Hips shooting up",
    "Forcing the transition with strength it does not have"),
   ("Pull high until the bar is at the sternum",
    "Rotate the wrists over the bar and lean the chest over it",
    "Keep the elbows high and the legs slightly behind you"),
   easier=("c2b_pullup", "pullup"), harder=("bar_muscle_up",),
   prereq=("c2b_pullup",), related=("bar_muscle_up", "ring_muscle_up"))

_d("bar_muscle_up",
   ("Lats", "Chest", "Triceps", "Shoulders"),
   ("Kipping", "Swinging the legs over instead of rotating",
    "Pressing away from the bar with the arms bent"),
   ("Pull explosively to chest-to-bar, then rotate over the bar fast",
    "Press to a straight-arm support above the bar",
    "Practise the transition on a low bar before the full movement"),
   easier=("mu_transition", "c2b_pullup"), harder=("ring_muscle_up",),
   prereq=("c2b_pullup", "mu_transition"), related=("mu_transition", "ring_muscle_up"))

_d("ring_muscle_up",
   ("Lats", "Chest", "Shoulders", "Forearms"),
   ("False grip lost on the way up", "Rings swinging apart",
    "Rushing the transition"),
   ("Use a false grip and pull the rings to the armpits",
    "Roll the shoulders over the rings and turn the elbows forward",
    "Press out to a support above the rings, then lower under control"),
   easier=("bar_muscle_up", "false_grip_hang"), harder=(),
   prereq=("false_grip_hang", "bar_muscle_up"), related=("bar_muscle_up", "ring_dip"))

_d("skin_the_cat",
   ("Lats", "Shoulders", "Core", "Forearms"),
   ("Tucking into a ball too fast", "Swinging through the bottom",
    "Forcing the range with an arched back"),
   ("Tuck the knees, rotate the hips back and over the bar",
    "Keep the arms straight and the shoulders active",
    "Reverse the same path on the way down and stay in control"),
   easier=("active_hang",), harder=("tuck_back_lever",),
   prereq=("active_hang",), related=("tuck_back_lever", "active_hang"))

_d("press_handstand",
   ("Shoulders", "Core", "Triceps", "Wrists"),
   ("Hips folding instead of pressing vertically", "Feet kicking up",
    "Shoulders collapsing in the bottom position"),
   ("From a straddle L-sit, press the hips up and over",
    "Push the floor away hard and keep the legs together at the top",
    "Build up with wall presses and straddle presses"),
   easier=("free_handstand", "wall_handstand"), harder=(),
   prereq=("free_handstand", "tuck_l_sit"), related=("free_handstand", "tuck_l_sit"))

# ================================================== EXPLOSIVE MOVEMENTS
_d("clap_pushup",
   ("Chest", "Triceps", "Front delts"),
   ("Hands landing too wide", "Wrists taking the impact",
    "Chest sagging during the flight"),
   ("Push hard enough to leave the floor, clap in the air",
    "Land with the hands under the shoulders and bent elbows",
    "Keep the body rigid and the core braced throughout"),
   easier=("pushup",), harder=("one_arm_pushup",),
   prereq=("pushup",), related=("pushup",))

_d("jump_squat",
   ("Quads", "Glutes", "Hamstrings", "Core"),
   ("Landing with straight knees", "Knees caving inwards",
    "Squatting too shallow to generate power"),
   ("Squat to full depth, then drive through the whole foot",
    "Land softly on the balls of the feet and immediately absorb",
    "Keep the chest tall and the landing quiet"),
   easier=("squat",), harder=("box_jump", "tuck_jump"),
   prereq=("squat",), related=("squat", "box_jump"))

_d("jump_lunge",
   ("Quads", "Glutes", "Core"),
   ("Landing on a straight leg", "Stance too narrow",
    "Hips twisting in the air"),
   ("Jump and switch the legs in the air",
    "Land softly in a lunge with the front knee behind the toes",
    "Keep the torso upright and the front heel planted"),
   easier=("lunge",), harder=("tuck_jump",),
   prereq=("split_squat", "lunge"), related=("lunge", "tuck_jump"))

_d("box_jump",
   ("Quads", "Glutes", "Core"),
   ("Knees driving into the box", "Landing flat-footed and heavy",
    "Box too high to control"),
   ("Jump and land on the box with the feet, not the shins",
    "Stand up fully on the box before stepping down",
    "Start with a low box and build the height gradually"),
   easier=("jump_squat", "step_up"), harder=(),
   prereq=("jump_squat",), related=("jump_squat", "step_up"))

_d("tuck_jump",
   ("Quads", "Core", "Hip flexors"),
   ("Landing with straight legs", "Knees not reaching the chest",
    "Back arching on landing"),
   ("Jump and tuck the knees up towards the chest",
    "Land on the balls of the feet with the knees bent",
    "Keep the core tight in the air and quiet on landing"),
   easier=("jump_squat",), harder=(),
   prereq=("jump_squat",), related=("jump_squat", "jump_lunge"))

_d("burpee",
   ("Full body", "Chest", "Quads", "Core"),
   ("Rounding the lower back in the plank", "Landing heavy from the jump",
    "Rushing the transitions"),
   ("Chest to the floor every rep, keep the plank rigid",
    "Jump up and reach overhead with straight arms",
    "Land with soft knees and control every transition"),
   easier=("pushup", "squat"), harder=("clap_pushup", "tuck_jump"),
   prereq=("pushup", "squat"), related=("pushup", "jump_squat"))
